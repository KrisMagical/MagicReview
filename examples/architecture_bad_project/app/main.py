from fastapi import FastAPI

from app.api.users import router as users_router
from app.api.orders import router as orders_router

app = FastAPI()
app.include_router(users_router)
app.include_router(orders_router)
