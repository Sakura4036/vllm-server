from pydantic import BaseModel, Field, RootModel
from typing import Dict, Optional, Any
from enum import Enum


class Status(str, Enum):
    STARTING = "starting"
    RUNNING = "running" 
    STOPPED = "stopped"


class ErrorResponse(BaseModel):
    status_code: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Error details")


class InstanceParams(BaseModel):
    model: Optional[str] = Field(None, description="Model name")
    port: Optional[int] = Field(None, description="Instance port")
    dtype: Optional[str] = Field(None, description="Data type used for model")
    kv_cache_dtype: Optional[str] = Field(None, description="Data type used for KV cache")
    trust_remote_code: Optional[bool] = Field(None, description="Whether to trust remote code")
    

class InstanceCreate(BaseModel):
    model_name: str = Field(..., description="Model name")
    params: Optional[Dict[str, Any]] = Field(default={}, description="Instance startup parameters")
    timeout: Optional[int] = Field(None, description="Instance timeout in seconds")


class InstanceInfo(BaseModel):
    instance_id: str = Field(..., description="Instance ID")
    model_name: str = Field(..., description="Model name")
    port: int = Field(..., description="Instance port")
    status: Status = Field(..., description="Instance status")
    last_active: float = Field(..., description="Last active timestamp")
    timeout: int = Field(..., description="Timeout in seconds")
    params: Dict[str, Any] = Field(..., description="Instance parameters")


class InstanceList(RootModel):
    root: Dict[str, InstanceInfo] = Field(..., description="List of instances")


class DeleteResponse(BaseModel):
    status: str = Field(..., description="Operation status") 