from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from instance_manager.manager import InstanceManager
from configs.app_config import app_config
import httpx

router = APIRouter()

instance_manager = InstanceManager()

def get_instance_url(port:int)->str:
    return f"{app_config.APP_HOST}:{port}"


@router.post("/instances")
async def create_instance(data: dict):
    """
    Create a new vllm instance. Accepts model_name, params, timeout.
    """
    model_name = data.get("model_name")
    params = data.get("params", {})
    timeout = data.get("timeout")
    if not model_name:
        raise HTTPException(400, "model_name is required")
    instance_id = instance_manager.create_instance(model_name, params, timeout)
    return {"instance_id": instance_id}

@router.get("/instances")
async def list_instances():
    """
    List all active vllm instances.
    """
    return instance_manager.list_instances()

@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    """
    Delete a vllm instance by id.
    """
    instance_manager.delete_instance(instance_id)
    return {"status": "deleted"}


async def proxy_to_vllm(instance_id: str, path: str, request: Request):
    """
    Proxy any request to the specified vllm instance.
    """
    inst = instance_manager.get_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Instance not found")
    url = f"{get_instance_url(inst)}{path}"
    method = request.method
    headers = dict(request.headers)
    body = await request.body()
    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.request(method, url, headers=headers, content=body, stream=True)
        # process stream response
        if resp.headers.get("content-type", "").startswith("text/event-stream"):
            return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=resp.headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


# support vLLM OpenAI-Compatible APIs
@router.api_route("/proxy/{instance_id}/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def vllm_api_proxy(instance_id: str, full_path: str, request: Request):
    """
    Proxy any OpenAI-Compatible API call to the specified vllm instance.
    Example: /proxy/{instance_id}/v1/completions
    """
    return await proxy_to_vllm(instance_id, f"/{full_path}", request) 