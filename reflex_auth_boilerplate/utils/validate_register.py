import bcrypt
from typing import Tuple


def validate_mail(mail: str) -> bool:
    return "@" in mail


def validate_password(password: str, confirm_password: str) -> Tuple[str, str]:
    if password != confirm_password:
        return "Passwords do not match", ""
    if len(password) < 1:
        return "Password must be at least 8 characters long", ""
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return "", pw_hash


def verify_password(password: str, pw_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), pw_hash.encode())
