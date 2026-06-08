class UserRepository:
    def create(self, payload):
        return {"id": payload["id"], "email": payload["email"]}

    def get(self, user_id):
        return {"id": user_id, "email": "user@example.com"}
