def apply_discount(price, percent):
    """Take `percent` off the price. percent is a whole number: 20 means 20% off."""
    return price - price * percent / 100
