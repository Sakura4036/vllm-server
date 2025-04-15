import requests
import time

# 默认等待实例 ready 的最大时间（秒）
WAIT_READY_TIMEOUT = 30

# 支持的 OpenAI API 路径
OPENAI_PATHS = [
    '/v1/chat/completions',
    '/v1/completions',
    '/v1/models',
]

def get_or_create_instance(instance_manager, model_name: str, timeout: int = 600):
    """
    Get or create a vllm instance for the given model name.
    If not exists, create and wait until ready.
    """
    # 查找已存在实例
    for iid, inst in instance_manager.instances.items():
        if inst.model_name == model_name and inst.status == 'running':
            inst.touch()
            return inst
    # 不存在则新建
    instance_id = instance_manager.create_instance(model_name, timeout)
    inst = instance_manager.get_instance(instance_id)
    # 等待实例 ready（简单 sleep，后续可优化为健康检查）
    for _ in range(WAIT_READY_TIMEOUT):
        try:
            resp = requests.get(f'http://localhost:{inst.port}/v1/models', timeout=2)
            if resp.status_code == 200:
                return inst
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f'Instance for model {model_name} not ready in {WAIT_READY_TIMEOUT}s')

def proxy_openai_request(instance_manager, path: str, request_method, request_data, request_headers):
    """
    Proxy OpenAI API request to the correct vllm instance based on model field.
    """
    # 解析模型名
    model_name = None
    timeout = 600
    if request_data:
        model_name = request_data.get('model')
        # 可选支持自定义失活时间
        if 'timeout' in request_data:
            timeout = int(request_data['timeout'])
    if not model_name:
        return {'message': 'model field is required in request body'}, 400
    # 获取或创建实例
    try:
        inst = get_or_create_instance(instance_manager, model_name, timeout)
    except Exception as e:
        return {'message': str(e)}, 500
    # 构造目标 URL
    target_url = f'http://localhost:{inst.port}{path}'
    # 处理流式请求
    is_stream = False
    if request_data and 'stream' in request_data:
        is_stream = bool(request_data['stream'])
    # 转发请求
    try:
        resp = requests.request(
            method=request_method,
            url=target_url,
            headers={k: v for k, v in request_headers.items() if k.lower() != 'host'},
            json=request_data,
            stream=is_stream,
            timeout=600
        )
        # 流式响应直接返回生成器
        if is_stream:
            def generate():
                for chunk in resp.iter_content(chunk_size=4096):
                    if chunk:
                        yield chunk
            return generate(), resp.status_code, resp.headers.items()
        # 非流式响应
        return resp.content, resp.status_code, resp.headers.items()
    except Exception as e:
        return {'message': f'Proxy error: {str(e)}'}, 500 