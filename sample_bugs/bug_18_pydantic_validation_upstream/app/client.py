from app.parser import parse_payload

def fetch_and_format(raw_data: dict):
    parsed = parse_payload(raw_data)
    return f"User {parsed['id']} at {parsed['timestamp']}"
