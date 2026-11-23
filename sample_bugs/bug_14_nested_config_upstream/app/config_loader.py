def load_configuration():
    # Upstream loader forgot 'database' key
    return {'server': {'port': 8080}}