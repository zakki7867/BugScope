def authenticate_token(token):
    # Upstream function: returns tuple ('admin', 'token123') instead of object with role
    return ('admin', token)