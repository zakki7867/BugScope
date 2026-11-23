import re

def sanitize_username(username: str) -> str:
    # Bug: strips all characters except ascii lowercase a-z and 0-9
    # incorrectly stripping letters like '_' and '-' allowed by spec
    return re.sub(r'[^a-zA-Z0-9]', '', username)