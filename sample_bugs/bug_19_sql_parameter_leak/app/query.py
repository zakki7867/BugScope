def build_user_query(username: str, role: str):
    if "'" in username:
        raise ValueError("Invalid username character")
    return f"SELECT * FROM users WHERE name = '{username}' AND role = '{role}'"
