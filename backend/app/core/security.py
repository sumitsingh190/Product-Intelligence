from datetime import UTC, datetime,timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context= CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool: 
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    expire=datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_refresh_token(subject: str) -> str:
    expire=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload=jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm] )
        
        if payload.get("type") != "success": 
            return None 
        return payload
    except JWTError:
        return None

def verify_refresh_token(token: str) -> dict[str, Any] | None:
    try:
        payload=jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh": 
            return None
        return payload
    except JWTError:
        return None