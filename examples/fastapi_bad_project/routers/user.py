from fastapi import APIRouter, Depends

from db import SessionLocal
from services import UserService, get_client, get_db

router = APIRouter()


@router.post("/users")
def create_user(payload, db=Depends(lambda: SessionLocal())):
    session = SessionLocal()
    service = UserService()
    if payload:
        if payload.get("active"):
            if payload.get("admin"):
                session.execute("select 1")
    return {"id": 1, "name": payload.get("name")}


@router.get("/users/{user_id}")
def get_user(user_id: int, client=Depends(get_client)):
    service = UserService()
    return {"id": user_id, "name": "Ada"}


@router.get("/healthy", response_model=dict)
def healthy(db=Depends(get_db)):
    return {"code": 0, "message": "ok", "data": {}}
