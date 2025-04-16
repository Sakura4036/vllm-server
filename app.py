from fastapi import FastAPI
from api.router import router
from configs import app_config
import uvicorn


app = FastAPI()

app.include_router(router)

def main():
    uvicorn.run("main:app", host=app_config.APP_HOST, port=app_config.APP_PORT, reload=app_config.APP_DEBUG)

if __name__ == "__main__":
    main()
