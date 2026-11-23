def parse_payload(data: dict):
    # Upstream parser expects int but receives ISO string
    return {"id": data["id"], "timestamp": int(data["timestamp"])}
