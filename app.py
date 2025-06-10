from fastapi import FastAPI
from api.router import router
from configs import app_config
from instance_manager import manager
import uvicorn
import asyncio
from contextlib import asynccontextmanager

# Background task for cleaning up expired instances
async def periodic_cleanup():
    while True:
        # Check for expired instances every 60 seconds
        await asyncio.sleep(60)
        print("Running scheduled cleanup of expired instances...")
        await manager.cleanup_expired()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background cleanup task when the application starts
    print("Starting background cleanup task...")
    cleanup_task = asyncio.create_task(periodic_cleanup())
    yield
    # Clean up the task when the application shuts down
    print("Stopping background cleanup task...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        print("Background task cancelled successfully.")


app = FastAPI(
    title="vLLM Server Management API",
    description="API service for managing and proxying multiple vLLM model instances",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.include_router(router)

def main():
    uvicorn.run("app:app", host=app_config.APP_HOST, port=app_config.APP_PORT, reload=app_config.APP_DEBUG)

if __name__ == "__main__":
    main()
