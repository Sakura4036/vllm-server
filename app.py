from fastapi import FastAPI
from api.router import router
from configs import app_config
import uvicorn


app = FastAPI(
    title="vLLM Server Management API",
    description="API service for managing and proxying multiple vLLM model instances",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.include_router(router)

def main():
    uvicorn.run("app:app", host=app_config.APP_HOST, port=app_config.APP_PORT, reload=app_config.APP_DEBUG)

if __name__ == "__main__":
    main()
