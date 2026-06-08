import os

from app.repositories.user_repository import UserRepository
from app.db import SessionLocal


def create_user(payload, a, b, c):
    repo = UserRepository()
    db = SessionLocal()
    db.execute("SELECT * FROM users")
    os.system("echo unsafe")
    if payload:
        if a:
            if b:
                return repo.create(payload)
    return {"ok": True}
