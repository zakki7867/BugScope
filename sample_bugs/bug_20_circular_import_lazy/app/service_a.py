from app.service_b import compute_b

def compute_a(val: int) -> int:
    return compute_b(val) + 1
