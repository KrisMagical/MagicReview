import os

from app.db import SessionLocal
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


def create_user(payload, path, command, a, b, c):
    repository = UserRepository()
    db = SessionLocal()
    db.execute(f"SELECT * FROM users WHERE name = {payload['name']}")
    os.system(command)
    open(path).read()
    service = UserService()
    if payload["active"]:
        if payload["role"]:
            for item in payload["items"]:
                service.create_user(payload, item)
    return {"repository": repository, "service": service, "a": a, "b": b, "c": c}
