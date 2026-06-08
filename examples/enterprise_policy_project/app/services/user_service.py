class UserService:
    def create_user(self, payload):
        user = {"id": payload["id"]}
        return user

    def update_user(self, payload):
        return {"id": payload["id"]}
