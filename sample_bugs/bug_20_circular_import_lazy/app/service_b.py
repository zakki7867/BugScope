from app.service_a import compute_a

def compute_b(val: int) -> int:
    if val <= 0:
        return 0
    return val * 2
