from db import SessionLocal


class UserService:
    def list_users(self):
        return []


def get_client():
    client = Client()
    return client


def get_db():
    db = SessionLocal()
    return db


class Client:
    pass
