from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from instance_manager.manager import InstanceManager
from configs import app_config
import httpx
from typing import Dict

from .models import (
    InstanceCreate, 
    InstanceInfo, 
    DeleteResponse, 
    ErrorResponse
)

router = APIRouter()

instance_manager = InstanceManager()

def get_instance_url(port:int)->str:
    return f"{app_config.APP_HOST}:{port}"


@router.post(
    "/instances", 
    response_model=InstanceInfo,
    responses={
        200: {"model": InstanceInfo, "description": "Instance created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Create new vLLM instance",
    description="Create a new vLLM model instance with specified model name, parameters and timeout"
)
async def create_instance(data: InstanceCreate):
    """
    Create a new vLLM instance
    
    - **model_name**: Name of the model (required)
    - **params**: Optional parameters like dtype, trust_remote_code, etc.
    - **timeout**: Timeout in seconds, default value is determined by server configuration
    
    Returns the created instance information
    """
    if not data.model_name:
        raise HTTPException(400, detail="model_name is required")
    try:
        instance = instance_manager.create_instance(data.model_name, data.params, data.timeout)
        return instance.status_dict
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to create instance: {str(e)}")

@router.get(
    "/instances",
    response_model=Dict[str, InstanceInfo],
    responses={
        200: {"model": Dict[str, InstanceInfo], "description": "Instance list retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get all vLLM instances",
    description="List all currently active vLLM instances and their status information"
)
async def list_instances():
    """
    Get a list of all active vLLM instances
    
    Returns a mapping from instance ID to instance details
    """
    try:
        return instance_manager.list_instances()
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to retrieve instance list: {str(e)}")

@router.delete(
    "/instances/{instance_id}",
    response_model=DeleteResponse,
    responses={
        200: {"model": DeleteResponse, "description": "Instance deleted successfully"},
        404: {"model": ErrorResponse, "description": "Instance not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Delete vLLM instance",
    description="Delete a specified vLLM instance by its ID"
)
async def delete_instance(instance_id: str):
    """
    Delete a vLLM instance by ID
    
    - **instance_id**: ID of the instance to delete
    
    Returns status information upon successful deletion
    """
    try:
        if not instance_manager.get_instance(instance_id):
            raise HTTPException(404, detail=f"Instance {instance_id} not found")
        instance_manager.delete_instance(instance_id)
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to delete instance: {str(e)}")


async def proxy_to_vllm(instance_id: str, path: str, request: Request):
    """
    Proxy any request to the specified vLLM instance.
    
    - **instance_id**: Target instance ID
    - **path**: Request path
    - **request**: Original request object
    
    Returns the response from the vLLM instance
    """
    inst = instance_manager.get_instance(instance_id)
    if not inst:
        raise HTTPException(404, detail="Instance not found")
    url = f"{get_instance_url(inst.port)}{path}"
    method = request.method
    headers = dict(request.headers)
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.request(method, url, headers=headers, content=body, stream=True)
            # Process stream response
            if resp.headers.get("content-type", "").startswith("text/event-stream"):
                return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=resp.headers)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        raise HTTPException(500, detail=f"Proxy request failed: {str(e)}")


# Support vLLM OpenAI-Compatible APIs
@router.api_route(
    "/proxy/{instance_id}/{full_path:path}", 
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    summary="vLLM API Proxy",
    description="Proxy requests to the specified vLLM instance, supporting OpenAI-compatible APIs",
    responses={
        200: {"description": "Request proxied successfully"},
        404: {"model": ErrorResponse, "description": "Instance not found"},
        500: {"model": ErrorResponse, "description": "Proxy request failed"}
    }
)
async def vllm_api_proxy(instance_id: str, full_path: str, request: Request):
    """
    Proxy any OpenAI-compatible API call to the specified vLLM instance
    
    - **instance_id**: Target instance ID
    - **full_path**: Full path to proxy
    
    Example: /proxy/{instance_id}/v1/completions
    
    Returns the response from the vLLM instance
    """
    return await proxy_to_vllm(instance_id, f"/{full_path}", request) 