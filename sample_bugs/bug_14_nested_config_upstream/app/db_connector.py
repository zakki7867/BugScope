from app.config_loader import load_configuration

def connect_db():
    cfg = load_configuration()
    # Crashes with KeyError: 'database'
    return f'Connecting to {cfg["database"]["host"]}'