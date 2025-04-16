# vllm-server

<p align="center">
  <a href="./README.md">README</a> |
  <a href="https://github.com/vllm-project/vllm">vLLM</a> |
  <a href="https://docs.vllm.ai/en/latest/index.html">vLLM Doc</a>
</p>

一个支持多实例管理和 API 代理的 vLLM OpenAI-Compatible Server 管理器，支持所有 API 类型（Completions、Embeddings、Re-rank 等），支持全部启动参数自定义，并通过 dotenv 管理环境变量。

## 功能特性
- 支持多 vLLM 实例的启动、停止、自动过期与管理
- 代理 vLLM OpenAI-Compatible Server 的全部 API（Completions、Embeddings、Re-rank 等）
- 实例启动参数可完全自定义（API 传参或 .env 配置）
- 使用 `.env` 和 `python-dotenv` 管理环境变量
- 清晰、模块化的项目结构，便于扩展

## 项目结构
```
/instance_manager/manager.py  # vLLM 实例管理核心逻辑
/api/router.py               # API 代理层（FastAPI）
/configs/app_config.py       # 配置管理
/utils/                      # 工具函数
env.example                  # 默认配置
app.py                       # 应用入口
```

## 环境变量（.env）
| 名称                        | 说明                        | 默认值    |
|-----------------------------|-----------------------------|-----------|
| APP_HOST                    | FastAPI 服务器主机          | 0.0.0.0   |
| APP_PORT                    | FastAPI 服务器端口          | 5000      |
| APP_DEBUG                   | 启用调试模式                | false     |
| VLLM_BASE_PORT              | vLLM 实例起始端口           | 9000      |
| VLLM_MAX_INSTANCES          | 最大实例数                  | 20        |
| VLLM_DEFAULT_DTYPE          | 默认 dtype                  | auto      |
| VLLM_DEFAULT_KV_CACHE_DTYPE | 默认 kv-cache-dtype         | auto      |
| VLLM_DEFAULT_TRUST_REMOTE_CODE | 是否信任远程代码         | true      |
| VLLM_DEFAULT_TIMEOUT        | 实例自动过期时间（秒）      | 600       |
| VLLM_CONFIG                 | 可选的 vLLM 配置文件路径    | null      |

## 使用方法
1. 克隆仓库并安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 编辑 `.env` 配置默认 vLLM 启动参数。
3. 启动服务器：
   ```bash
   python app.py
   ```
4. 使用 API 创建和管理 vLLM 实例：

### 创建实例
```bash
curl -X POST http://localhost:5000/instances -H "Content-Type: application/json" \
  -d '{"model_name": "NousResearch/Meta-Llama-3-8B-Instruct", "params": {"dtype": "float16"}}'
```

### 列出实例
```bash
curl http://localhost:5000/instances
```

### 使用 OpenAI 兼容 API
```bash
# 首先从 /instances 端点获取 instance_id
curl -X POST http://localhost:5000/proxy/{instance_id}/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "NousResearch/Meta-Llama-3-8B-Instruct", "prompt": "你好，世界！", "max_tokens": 100}'
```

## API 端点
- `POST /instances` - 创建新的 vLLM 实例
- `GET /instances` - 列出所有活跃实例
- `DELETE /instances/{instance_id}` - 删除实例
- `ANY /proxy/{instance_id}/{path}` - 代理任何请求到特定实例

---

更多细节请参考 [vLLM OpenAI-Compatible Server 官方文档](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html) 