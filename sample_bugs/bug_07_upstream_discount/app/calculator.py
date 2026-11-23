from app.parser import parse_order_payload

def compute_final_bill(raw_payload):
    order = parse_order_payload(raw_payload)
    # Crashes here because parser omitted 'discount'
    return order['price'] - order['discount']