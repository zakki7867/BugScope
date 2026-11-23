def format_user_profile(user_dict):
    name = user_dict['name']
    # Missing email key causes KeyError
    email = user_dict['email']
    return f'{name} <{email}>'