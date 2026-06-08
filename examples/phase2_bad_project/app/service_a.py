from app import service_b


def call_b() -> str:
    return service_b.call_a()
