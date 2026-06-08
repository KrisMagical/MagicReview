from app.api.users import create_user


def run():
    return create_user({"id": 1})
