from app.auth import authenticate_token

def has_admin_access(token):
    user = authenticate_token(token)
    # Crashes with AttributeError: 'tuple' object has no attribute 'role'
    return user.role == 'admin'