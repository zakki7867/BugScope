def validate_session(session):
    if session is None:
        return False
    token = session.get('token')
    # AttributeError when token is None
    return token.lower().startswith('sess_')