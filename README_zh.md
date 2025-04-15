# vLLM 多模型部署与管理平台

<p align="center">
  <a href="./README.md">README</a> |
  <a href="[./README_zh.md](https://github.com/vllm-project/vllm)">vLLM</a> |
  <a href="https://docs.vllm.ai/en/latest/index.html">vLLM Doc</a>
</p>

本项目提供了对多个 vLLM 模型实例的统一管理与代理服务，暴露 OpenAI 兼容 API，支持动态创建、管理和请求转发。

## 主要功能

- 支持通过 OpenAI 兼容 API 路由到不同 vLLM 实例（多模型、多端口）
- 实例自动失活与资源回收
- 实例管理接口（创建、查询、删除）
- 健康检查接口
- 支持并发部署和请求
- 详细英文注释，函数式风格

## 安装与运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（默认端口5000）
python app.py
```

## API 接口

### 1. 实例管理
- `GET /instances`：查询所有激活实例
- `POST /instances`：新建/激活实例
  - Body: `model_name`（必填），`timeout`（可选，单位秒，默认600）
- `DELETE /instances/<instance_id>`：删除实例

### 2. OpenAI 兼容接口
- `POST /v1/chat/completions`：与 OpenAI API 完全兼容，需在 body 中指定 `model` 字段
- `POST /v1/completions`：同上
- `GET /v1/models`：返回所有已激活模型信息

### 3. 健康检查
- `GET /health`：返回服务健康状态、实例数、vllm 子进程数

## 典型用例

### 创建并激活模型实例
```bash
curl -X POST http://localhost:5000/instances -H "Content-Type: application/json" -d '{"model_name": "facebook/opt-125m"}'
```

### 使用 OpenAI 兼容接口进行推理
```python
import requests
resp = requests.post(
    'http://localhost:5000/v1/chat/completions',
    json={
        "model": "facebook/opt-125m",
        "messages": [{"role": "user", "content": "你好"}]
    }
)
print(resp.json())
```

### 查询所有激活实例
```bash
curl http://localhost:5000/instances
```

### 删除实例
```bash
curl -X DELETE http://localhost:5000/instances/<instance_id>
```

### 健康检查
```bash
curl http://localhost:5000/health
```

## 项目结构

- `app.py` - Flask 主应用与 API 定义
- `instance_manager.py` - 实例与进程管理逻辑
- `router.py` - 请求路由与代理逻辑

## 其他说明
- 每个 vLLM 实例独立端口，自动分配，失活后自动回收
- 支持流式和非流式响应
- 详细代码注释便于二次开发

## License

MIT 