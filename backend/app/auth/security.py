from hashlib import sha256
from secrets import token_urlsafe
from pwdlib import PasswordHash

passwords = PasswordHash.recommended()
# Same expensive verification path for an unknown username.
DUMMY_HASH = passwords.hash(token_urlsafe(32))
COOKIE_NAME = "almanac_session"

def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()

def new_token() -> str:
    return token_urlsafe(32)
