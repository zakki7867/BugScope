def add_transaction(amount, history=[]):
    """Return a NEW history list with the amount added."""
    history.append(amount)
    return history


def balance(history):
    return sum(history)
