import subprocess
import threading
import time
from typing import Dict, Optional

# 配置可用端口范围
BASE_PORT = 9000
MAX_INSTANCES = 20

class VLLMInstance:
    """
    Class representing a single vllm server instance.
    """
    def __init__(self, model_name: str, port: int, timeout: int = 600):
        self.model_name = model_name
        self.port = port
        self.timeout = timeout  # In seconds
        self.last_active = time.time()
        self.process: Optional[subprocess.Popen] = None
        self.status = 'starting'  # starting, running, stopped

    def start(self):
        """
        Start the vllm server as a subprocess on the specified port.
        """
        # 启动 vllm OpenAI-Compatible Server
        cmd = [
            'python', '-m', 'vllm.entrypoints.openai.api_server',
            '--model', self.model_name,
            '--port', str(self.port)
        ]
        self.process = subprocess.Popen(cmd)
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

class InstanceManager:
    """
    Class to manage all vllm server instances, including creation, deletion, and expiration.
    """
    def __init__(self):
        self.instances: Dict[str, VLLMInstance] = {}  # key: instance_id
        self.lock = threading.Lock()
        self.used_ports = set()

    def _allocate_port(self) -> int:
        """
        Allocate an available port for a new instance.
        """
        for port in range(BASE_PORT, BASE_PORT + MAX_INSTANCES):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        raise RuntimeError('No available ports for new vllm instance.')

    def _release_port(self, port: int):
        """
        Release a port when an instance is stopped.
        """
        self.used_ports.discard(port)

    def create_instance(self, model_name: str, timeout: int = 600) -> str:
        """
        Create and start a new vllm instance for the given model.
        Returns the instance_id.
        """
        with self.lock:
            port = self._allocate_port()
            instance_id = f"{model_name.replace('/', '_')}_{port}"
            instance = VLLMInstance(model_name, port, timeout)
            instance.start()
            self.instances[instance_id] = instance
            return instance_id

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
            iid: {
                'model_name': inst.model_name,
                'port': inst.port,
                'status': inst.status,
                'last_active': inst.last_active,
                'timeout': inst.timeout
            }
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