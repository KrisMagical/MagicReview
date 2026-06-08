from fastapi import FastAPI

from routers.user import router

app = FastAPI()
app.include_router(router)
