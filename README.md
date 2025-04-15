# vllm-server: A vLLM Instance Manager

<p align="center">
  <a href="./README_zh.md">中文</a> |
  <a href="[./README_zh.md](https://github.com/vllm-project/vllm)">vllm</a> |
  <a href="https://docs.vllm.ai/en/latest/index.html">vllm doc</a>
</p>

This project provides a management and proxy service for multiple vLLM model instances, exposing an OpenAI-compatible API. It allows you to dynamically create, manage, and proxy requests to vLLM model servers.


## Features

- Route OpenAI-compatible API requests to different vLLM instances (multi-model, multi-port)
- Automatic instance expiration and resource recycling
- Instance management API (create, list, delete)
- Health check endpoint
- Support for concurrent deployment and requests
- Detailed English code comments, functional style

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the service (default port 5000)
python app.py
```

## API Endpoints

### 1. Instance Management
- `GET /instances`: List all active instances
- `POST /instances`: Create/activate an instance
  - Body: `model_name` (required), `timeout` (optional, seconds, default 600)
- `DELETE /instances/<instance_id>`: Delete an instance

### 2. OpenAI-Compatible API
- `POST /v1/chat/completions`: Fully compatible with OpenAI API, must specify `model` in body
- `POST /v1/completions`: Same as above
- `GET /v1/models`: List all active models

### 3. Health Check
- `GET /health`: Returns service health, instance count, vllm subprocess count

## Typical Usage

### Create and activate a model instance
```bash
curl -X POST http://localhost:5000/instances -H "Content-Type: application/json" -d '{"model_name": "facebook/opt-125m"}'
```

### Use OpenAI-compatible API for inference
```python
import requests
resp = requests.post(
    'http://localhost:5000/v1/chat/completions',
    json={
        "model": "facebook/opt-125m",
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
print(resp.json())
```

### List all active instances
```bash
curl http://localhost:5000/instances
```

### Delete an instance
```bash
curl -X DELETE http://localhost:5000/instances/<instance_id>
```

### Health check
```bash
curl http://localhost:5000/health
```

## Project Structure

- `app.py` - Main Flask application and API definitions
- `instance_manager.py` - Instance and process management logic
- `router.py` - Request routing and proxy logic

## Other Notes
- Each vLLM instance runs on an independent port, automatically allocated and recycled after expiration
- Supports both streaming and non-streaming responses
- Detailed code comments for easy secondary development

## License

MIT

---

For the Chinese version of the documentation, please see [README_zh.md](README_zh.md).