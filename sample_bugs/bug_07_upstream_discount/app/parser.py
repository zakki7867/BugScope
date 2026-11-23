def parse_order_payload(raw_json):
    # Upstream function: forgot to provide default for 'discount'
    return {'item': raw_json.get('item', 'unknown'), 'price': raw_json.get('price', 0.0)}