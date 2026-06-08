from app.repositories.user_repository import UserRepository
from app.services.order_service import OrderService


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository
        self.order_service = OrderService()

    def create_user(self, payload):
        user = self.repository.create(payload)
        self.send_welcome_email(user)
        self.charge_signup_bonus(user)
        return user

    def send_welcome_email(self, user):
        return f"welcome {user['email']}"

    def send_invoice_email(self, user, order):
        return f"invoice {user['email']} {order['id']}"

    def charge_signup_bonus(self, user):
        return {"payment_id": user["id"]}

    def cancel_orders_for_user(self, user_id):
        return self.order_service.cancel_all(user_id)
