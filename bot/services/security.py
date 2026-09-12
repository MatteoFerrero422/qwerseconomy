"""
Безопасное хэширование паролей (PBKDF2-HMAC-SHA256 со случайной солью).
Пароли никогда не хранятся и не логируются в открытом виде.
"""
import hashlib
import secrets

_ITERATIONS = 100_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Возвращает (hash, salt). Если salt не передан — генерирует новый."""
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    ).hex()
    return pwd_hash, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Безопасно (constant-time) сверяет введённый пароль с хэшем."""
    candidate_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate_hash, expected_hash)
