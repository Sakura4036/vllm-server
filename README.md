# vllm-server

<p align="center">
  <a href="./README_zh.md">中文</a> |
  <a href="https://github.com/vllm-project/vllm">vllm</a> |
  <a href="https://docs.vllm.ai/en/latest/index.html">vllm doc</a>
</p>

A multi-instance manager and API proxy for vLLM OpenAI-Compatible Server, supporting all API types (Completions, Embeddings, Re-rank, etc.), full launch parameter customization, and environment variable management via dotenv.

## Features
- Manage multiple vLLM server instances (start/stop/list/auto-expire)
- Proxy all vLLM OpenAI-Compatible Server APIs (Completions, Embeddings, Re-rank, etc.)
- Launch vLLM instances with fully customizable parameters (via API or .env)
- Environment variable management with `.env` and `python-dotenv`
- Clear, modular project structure

## Project Structure
```
/instance_manager/manager.py  # vLLM instance management logic
/api/router.py               # API proxy layer using FastAPI
/configs/app_config.py       # Configuration management
/utils/                      # Utility functions
env.example                  # Default configuration
app.py                       # Application entry point
```

## Environment Variables (.env)
| Name                        | Description                        | Default   |
|-----------------------------|------------------------------------|-----------|
| APP_HOST                    | Host for FastAPI server            | 0.0.0.0   |
| APP_PORT                    | Port for FastAPI server            | 5000      |
| APP_DEBUG                   | Enable debug mode                  | false     |
| VLLM_BASE_PORT              | Base port for vLLM instances       | 9000      |
| VLLM_MAX_INSTANCES          | Max number of vLLM instances       | 20        |
| VLLM_DEFAULT_DTYPE          | Default dtype for vLLM             | auto      |
| VLLM_DEFAULT_KV_CACHE_DTYPE | Default kv-cache-dtype             | auto      |
| VLLM_DEFAULT_TRUST_REMOTE_CODE | Trust remote code               | true      |
| VLLM_DEFAULT_TIMEOUT        | Instance auto-expire timeout (sec) | 600       |
| VLLM_CONFIG                 | Optional vLLM config file path     | null      |

## Usage
1. Clone the repo and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Edit `.env` to set your default vLLM parameters.
3. Start the server:
   ```bash
   python app.py
   ```
4. Use the API to create and manage vLLM instances:

### Creating an Instance
```bash
curl -X POST http://localhost:5000/instances -H "Content-Type: application/json" \
  -d '{"model_name": "NousResearch/Meta-Llama-3-8B-Instruct", "params": {"dtype": "float16"}}'
```

### Listing Instances
```bash
curl http://localhost:5000/instances
```

### Using the OpenAI-Compatible API
```bash
# First get your instance_id from the /instances endpoint
curl -X POST http://localhost:5000/proxy/{instance_id}/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "NousResearch/Meta-Llama-3-8B-Instruct", "prompt": "Hello, world!", "max_tokens": 100}'
```

## API Endpoints
- `POST /instances` - Create a new vLLM instance
- `GET /instances` - List all active instances
- `DELETE /instances/{instance_id}` - Delete an instance
- `ANY /proxy/{instance_id}/{path}` - Proxy any request to a specific instance

---

For more details, see [vLLM OpenAI-Compatible Server documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)