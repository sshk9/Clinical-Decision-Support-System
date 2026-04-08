from __future__ import annotations
import hashlib
import secrets
from .database import get_user_by_username, create_user


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_credentials(username: str, password: str) -> bool:
    """Returns True if username/password match a record in the database."""
    user = get_user_by_username(username)
    if user is None:
        return False
    stored_hash, salt = user
    return hash_password(password, salt) == stored_hash


def register_user(username: str, password: str) -> None:
    """Creates a new user with a hashed password."""
    salt = secrets.token_hex(16)
    hashed = hash_password(password, salt)
    create_user(username, hashed, salt)