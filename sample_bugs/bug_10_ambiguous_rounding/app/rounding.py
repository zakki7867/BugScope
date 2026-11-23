def split_cents(amount, parts):
    # Ambiguous business logic: should remainder cents round up or round even?
    raw = amount / parts
    return round(raw, 2)