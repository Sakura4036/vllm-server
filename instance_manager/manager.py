import subprocess
import threading
import time
import json
import os
import signal
import redis
import httpx
import asyncio
from typing import Dict, Optional
from configs import app_config


class VLLMConfigManager:
    def __init__(self):
        self.config_file = app_config.VLLM_CONFIG
        self.default_config = {
            'dtype': app_config.VLLM_DEFAULT_DTYPE,
            'kv_cache_dtype': app_config.VLLM_DEFAULT_KV_CACHE_DTYPE,
            'trust_remote_code': app_config.VLLM_DEFAULT_TRUST_REMOTE_CODE,
        }
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """
        load from config.json 
        """
        if not self.config_file or not os.path.exists(self.config_file):
            return self.default_config.copy()
        
        try:
            with open(self.config_file, 'r') as f:
                file_config = json.load(f)
                merged_config = self.default_config.copy()
                merged_config.update(file_config)
                return merged_config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Loading config error: {self.config_file}: {str(e)}")
            return self.default_config.copy()
    
    def get_config(self) -> dict:
        return self.config.copy()
    
    def get_merged_config(self, user_params: dict = None) -> dict:
        merged = self.config.copy()
        if user_params:
            merged.update(user_params)
        return merged

    @property
    def status_dict(self) -> dict:
        return self.to_dict()


class VLLMInstance:
    """
    Class representing a single vllm server instance.
    The state of this instance is meant to be stored and reconstructed from Redis.
    """

    def __init__(self, model_name: str, port: int, params: dict, timeout: int = 600, pid: int = None, last_active: float = None):
        self.model_name = model_name
        self.port = port
        self.params = params
        self.timeout = timeout
        self.last_active = last_active or time.time()
        self.process: Optional[asyncio.subprocess.Process] = None
        self.pid = pid
        # Status flow: starting -> health_checking -> running | failed
        self.status = 'starting'
        self.instance_id = f"{model_name.replace('/', '_')}_{port}"

    def to_dict(self) -> dict:
        """
        Serialize instance data to a dictionary for storage.
        """
        return {
            "instance_id": self.instance_id,
            "model_name": self.model_name,
            "port": self.port,
            "status": self.status,
            "last_active": self.last_active,
            "timeout": self.timeout,
            "params": self.params,
            "pid": self.pid
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VLLMInstance':
        """
        Deserialize instance data from a dictionary.
        """
        return cls(
            model_name=data['model_name'],
            port=data['port'],
            params=data['params'],
            timeout=data['timeout'],
            pid=data.get('pid'),
            last_active=data['last_active']
        )

    async def start(self):
        """
        Start the vllm server as a subprocess using asyncio.
        """
        # Set up environment variables for HuggingFace
        env = os.environ.copy()
        
        # Configure HuggingFace endpoint if available
        if app_config.HF_ENDPOINT:
            env['HF_ENDPOINT'] = app_config.HF_ENDPOINT
        
        # Configure HTTP proxy if available
        if app_config.HTTP_PROXY:
            env['HTTP_PROXY'] = app_config.HTTP_PROXY
            env['HTTPS_PROXY'] = app_config.HTTP_PROXY
        
        # Configure download cache directory if specified
        if app_config.HF_HOME:
            env['HF_HOME'] = app_config.HF_HOME
        
        # Build vllm OpenAI-Compatible Server command
        cmd = [
            'python', '-m', 'vllm.entrypoints.openai.api_server',
            '--model', self.model_name,
            '--port', str(self.port)
        ]
        # Add extra params
        for k, v in self.params.items():
            if k in ['model', 'port']:
                continue
            if isinstance(v, bool):
                if v:
                    cmd.append(f'--{k}')
            else:
                cmd.extend([f'--{k.replace("_", "-")}', str(v)])
                
        print(f"Starting vLLM instance with command: {' '.join(cmd)}")
        self.process = await asyncio.create_subprocess_exec(*cmd, env=env)
        self.pid = self.process.pid # Store the process ID
        self.last_active = time.time()

    async def stop(self):
        """
        Stop the vllm server subprocess asynchronously.
        """
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                print(f"Process {self.pid} did not terminate gracefully, killing.")
                self.process.kill()
                await self.process.wait()
        elif self.pid:
            # Fallback for processes restored from Redis without a process handle
            try:
                os.kill(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                # Process already dead
                pass
            except Exception as e:
                print(f"Error terminating process {self.pid} with SIGTERM: {e}")
                try:
                    os.kill(self.pid, signal.SIGKILL) # Force kill
                except Exception as kill_e:
                    print(f"Error force-killing process {self.pid} with SIGKILL: {kill_e}")
        
        self.status = 'stopped'

    def touch(self):
        """
        Update the last active time to now.
        """
        self.last_active = time.time()

    def is_expired(self) -> bool:
        """
        Check if the instance has expired (inactive for longer than timeout).
        """
        return (time.time() - self.last_active) > self.timeout
    
    @property
    def status_dict(self) -> dict:
        return self.to_dict()

class InstanceManager:
    """
    Class to manage all vllm server instances using Redis as the backend.
    This makes the manager stateless and scalable.
    """
    INSTANCE_KEY_PREFIX = "vllm_instance"
    PORT_SET_KEY = "vllm_ports_used"

    def __init__(self):
        self.redis = redis.Redis(
            host=app_config.REDIS_HOST,
            port=app_config.REDIS_PORT,
            db=app_config.REDIS_DB,
            decode_responses=True
        )
        self.lock = threading.Lock() # Lock for port allocation
        self.config_manager = VLLMConfigManager()

    def _get_instance_key(self, instance_id: str) -> str:
        return f"{self.INSTANCE_KEY_PREFIX}:{instance_id}"

    def _allocate_port(self) -> int:
        """
        Allocate an available port from the configured range using Redis.
        """
        with self.lock:
            for port in range(app_config.VLLM_BASE_PORT, app_config.VLLM_BASE_PORT + app_config.VLLM_MAX_INSTANCES):
                if self.redis.sadd(self.PORT_SET_KEY, port):
                    return port
            raise RuntimeError('No available ports for new vllm instance.')

    def _release_port(self, port: int):
        """
        Release a port back to the pool in Redis.
        """
        self.redis.srem(self.PORT_SET_KEY, port)

    async def create_instance(self, model_name: str, params: dict = None, timeout: int = None) -> VLLMInstance:
        """
        Create, start, and health-check a new vllm instance.
        The entire process is atomic from the user's perspective.
        """
        port = self._allocate_port()
        instance = VLLMInstance(
            model_name,
            port,
            self.config_manager.get_merged_config(params),
            timeout or app_config.VLLM_DEFAULT_TIMEOUT
        )
        instance_key = self._get_instance_key(instance.instance_id)

        try:
            # Synchronously start the process
            await instance.start()
            if not instance.pid:
                raise RuntimeError("Failed to get PID for the instance process.")

            # Asynchronously perform health check
            instance.status = 'health_checking'
            self.redis.set(instance_key, json.dumps(instance.to_dict()))

            health_check_url = f"http://127.0.0.1:{instance.port}/docs"
            health_check_timeout = 120  # 2 minutes, as model loading can be slow

            is_healthy = await self._perform_health_check(health_check_url, health_check_timeout)
            
            if is_healthy:
                instance.status = 'running'
                print(f"Instance {instance.instance_id} is healthy and running.")
                self.redis.set(instance_key, json.dumps(instance.to_dict()))
                return instance
            else:
                print(f"Health check failed for {instance.instance_id}. Cleaning up.")
                await instance.stop()
                self._release_port(port)
                self.redis.delete(instance_key)
                raise RuntimeError(f"Instance {instance.instance_id} failed health check.")

        except Exception as e:
            # Generic cleanup for any failure during the process
            print(f"An error occurred during instance creation: {e}. Cleaning up.")
            self._release_port(port)
            self.redis.delete(instance_key)
            if instance and instance.pid:
                await instance.stop()
            raise e

    async def _perform_health_check(self, url: str, timeout: int) -> bool:
        """
        Polls a URL until it returns a 200 status or until timeout.
        """
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                try:
                    response = await client.get(url, timeout=5)
                    if response.status_code == 200:
                        return True
                except (httpx.RequestError, httpx.Timeout):
                    # Service not yet available, wait and retry
                    await asyncio.sleep(2)
        return False

    def get_instance(self, instance_id: str) -> Optional[VLLMInstance]:
        """
        Get an instance by its ID from Redis.
        """
        instance_key = self._get_instance_key(instance_id)
        instance_data = self.redis.get(instance_key)
        if instance_data:
            return VLLMInstance.from_dict(json.loads(instance_data))
        return None

    async def delete_instance(self, instance_id: str):
        """
        Stop and remove an instance by its ID from Redis asynchronously.
        """
        instance = self.get_instance(instance_id)
        if instance:
            await instance.stop()
            self._release_port(instance.port)
            self.redis.delete(self._get_instance_key(instance_id))

    def list_instances(self) -> Dict[str, dict]:
        """
        List all active instances with their status from Redis.
        """
        instance_keys = self.redis.keys(f"{self.INSTANCE_KEY_PREFIX}:*")
        instances = {}
        if instance_keys:
            instance_data_list = self.redis.mget(instance_keys)
            for data in instance_data_list:
                if data:
                    instance_dict = json.loads(data)
                    instances[instance_dict['instance_id']] = instance_dict
        return instances

    async def cleanup_expired(self):
        """
        Stop and remove all expired instances based on data in Redis.
        """
        instance_keys = self.redis.keys(f"{self.INSTANCE_KEY_PREFIX}:*")
        if not instance_keys:
            return
            
        for key in instance_keys:
            data = self.redis.get(key)
            if data:
                instance = VLLMInstance.from_dict(json.loads(data))
                if instance.is_expired():
                    print(f"Instance {instance.instance_id} has expired. Cleaning up.")
                    await self.delete_instance(instance.instance_id)
    
    def touch_instance(self, instance: VLLMInstance):
        """
        Update the last_active time for an instance in Redis.
        """
        instance.touch()
        instance_key = self._get_instance_key(instance.instance_id)
        # Use a pipeline for atomic update if needed, but this is generally fine
        self.redis.set(instance_key, json.dumps(instance.to_dict())) 