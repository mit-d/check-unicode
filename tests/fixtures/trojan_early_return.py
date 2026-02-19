def check_access(user):
    """Check user access level.⁧ ;return True"""
    if user.is_admin:
        return True
    return False
