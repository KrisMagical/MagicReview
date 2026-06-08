def load_user(data, cursor):
    user = data.get("user")
    cursor.execute(f"SELECT * FROM users WHERE name = {user.name}")
    return user.name
