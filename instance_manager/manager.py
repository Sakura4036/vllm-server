import subprocess
import threading
import time
import json
import os
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


class VLLMInstance:
    """
    Class representing a single vllm server instance.
    """

    def __init__(self, model_name: str, port: int, params: dict, timeout: int = 600):
        self.model_name = model_name
        self.port = port
        self.params = params  # All vllm startup params
        self.timeout = timeout  # In seconds
        self.last_active = time.time()
        self.process: Optional[subprocess.Popen] = None
        self.status = 'starting'  # starting, running, stopped
        self.instance_id = f"{model_name.replace('/', '_')}_{port}"

    def start(self):
        """
        Start the vllm server as a subprocess on the specified port.
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
        self.process = subprocess.Popen(cmd, env=env)
        self.status = 'running'
        self.last_active = time.time()

    def stop(self):
        """
        Stop the vllm server subprocess.
        """
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
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
        return {
            "instance_id": self.instance_id,
            "model_name": self.model_name,
            "port": self.port,
            "status": self.status,
            "last_active": self.last_active,
            "timeout": self.timeout,
            "params": self.params
        }

class InstanceManager:
    """
    Class to manage all vllm server instances, including creation, deletion, and expiration.
    """

    def __init__(self):
        self.instances: Dict[str, VLLMInstance] = {}  # key: instance_id
        self.lock = threading.Lock()
        self.used_ports = set()
        self.config_manager = VLLMConfigManager()

    def _allocate_port(self) -> int:
        """
        Allocate an available port for a new instance.
        """
        for port in range(app_config.VLLM_BASE_PORT, app_config.VLLM_BASE_PORT + app_config.VLLM_MAX_INSTANCES):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        raise RuntimeError('No available ports for new vllm instance.')

    def _release_port(self, port: int):
        """
        Release a port when an instance is stopped.
        """
        self.used_ports.discard(port)

    def create_instance(self, model_name: str, params: dict = None, timeout: int = None) -> VLLMInstance:
        """
        Create and start a new vllm instance for the given model and params.
        Returns the instance object.
        """
        with self.lock:
            port = self._allocate_port()
            merged_params = self.config_manager.get_merged_config(params)
            merged_params['model'] = model_name
            merged_params['port'] = port
            
            instance = VLLMInstance(
                model_name,
                port,
                merged_params,
                timeout or app_config.VLLM_DEFAULT_TIMEOUT
            )
            instance.start()
            self.instances[instance.instance_id] = instance
            return instance

    def get_instance(self, instance_id: str) -> Optional[VLLMInstance]:
        """
        Get an instance by its ID.
        """
        return self.instances.get(instance_id)

    def delete_instance(self, instance_id: str):
        """
        Stop and remove an instance by its ID.
        """
        with self.lock:
            instance = self.instances.pop(instance_id, None)
            if instance:
                instance.stop()
                self._release_port(instance.port)

    def list_instances(self) -> Dict[str, dict]:
        """
        List all active instances with their status.
        """
        return {
            iid: inst.status_dict
            for iid, inst in self.instances.items()
        }

    def cleanup_expired(self):
        """
        Stop and remove all expired instances.
        """
        with self.lock:
            expired = [iid for iid, inst in self.instances.items() if inst.is_expired()]
            for iid in expired:
                self.delete_instance(iid) 