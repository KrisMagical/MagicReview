from fastapi import APIRouter

from app.repositories.user_repository import UserRepository
from app.services.order_service import OrderService
from app.services.user_service import UserService

router = APIRouter()


@router.post("/orders")
def create_order(payload):
    repository = UserRepository()
    user_service = UserService(repository)
    order_service = OrderService()
    user = repository.get(payload["user_id"])
    order = order_service.create_order(user, payload)
    user_service.send_invoice_email(user, order)
    return {"order": order}
