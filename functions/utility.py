import re


def is_valid_email(email: str) -> bool:
    """
    Simple email validator. Uses a regex to check if the email is valid.
    """
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}", email):
        return False
    return True


def max_length(value: str, max_length: int) -> bool:
    """
    Check if the value is less than or equal to the max length.
    """
    if len(value.strip()) > max_length:
        return False
    return True


def min_length(value: str, min_length: int) -> bool:
    """
    Check if the value is greater than or equal to the min length.
    """
    if len(value.strip()) < min_length:
        return False
    return True
