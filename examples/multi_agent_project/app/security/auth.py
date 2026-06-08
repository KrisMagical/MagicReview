SECRET_KEY = "secret"
API_KEY = "hardcoded-api-key"


def encode(jwt, payload):
    return jwt.encode(payload, "secret")
