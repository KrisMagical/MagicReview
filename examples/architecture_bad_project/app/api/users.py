from fastapi import APIRouter

from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

router = APIRouter()


@router.post("/users")
def create_user(payload):
    repository = UserRepository()
    service = UserService(repository)
    user = repository.create(payload)
    service.send_welcome_email(user)
    service.charge_signup_bonus(user)
    return {"id": user["id"], "email": user["email"]}
