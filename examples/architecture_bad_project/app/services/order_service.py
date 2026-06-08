class OrderService:
    def create_order(self, user, payload):
        return {"id": payload["id"], "user": user}

    def cancel_all(self, user_id):
        return []
