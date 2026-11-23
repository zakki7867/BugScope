def calculate_tax(income: float, rate_percent: float) -> float:
    # Bug: multiplied by percent directly instead of rate_percent / 100.0
    return income * (rate_percent / 10.0)