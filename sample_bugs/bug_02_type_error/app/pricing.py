def calculate_discounted_price(price: float, rate) -> float:
    # rate is passed as string '0.15'
    factor = 1.0 - rate
    return round(price * factor, 2)