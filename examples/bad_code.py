def risky(data, items, count, user_path, cursor):
    user = data.get("user")
    name = user.name
    first = items[0]
    token = data["token"]
    ratio = 100 / count
    handle = open(user_path)
    cursor.execute(f"SELECT * FROM users WHERE name = {name}")
    return handle.read(), first, token, ratio
