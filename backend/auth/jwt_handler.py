"""
JWT creation, verification, cookie setting.
Uses python-jose for JWT operations.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, Response, status
from jose import JWTError, jwt

# ─── Environment Variables ────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

# ─── Cookie Configuration ─────────────────────────────────────────────
COOKIE_NAME = "access_token"
COOKIE_HTTPONLY = True
COOKIE_SECURE = False  # Set True in production (requires HTTPS)
COOKIE_SAMESITE = "strict"
COOKIE_MAX_AGE = JWT_EXPIRY_HOURS * 3600  # Convert hours to seconds


def create_jwt(
    employee_id: str,
    role: str,
    department: str,
    name: str,
    session_id: Optional[str] = None,
) -> str:
    """
    Create a JWT with the FinSolve payload structure.

    Args:
        employee_id: Unique employee identifier
        role: User role (engineering, finance, marketing, hr, c_suite, employee)
        department: User department
        name: User display name
        session_id: Optional session ID (generated if not provided)

    Returns:
        Encoded JWT string
    """
    if session_id is None:
        session_id = str(uuid4())

    now = datetime.now(timezone.utc)
    payload = {
        "sub": employee_id,
        "role": role,
        "department": department,
        "name": name,
        "session_id": session_id,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    """
    Verify and decode a JWT.

    Args:
        token: JWT string to verify

    Returns:
        Decoded payload dictionary

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def set_jwt_cookie(response: Response, token: str) -> None:
    """
    Set the JWT as an httpOnly cookie on the response.

    Args:
        response: FastAPI Response object
        token: JWT string to set as cookie
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
    )


def get_role_from_token(token: str) -> str:
    """
    Extract and return the role from a verified JWT.

    Args:
        token: JWT string to extract role from

    Returns:
        Role string (engineering, finance, marketing, hr, c_suite, employee)

    Raises:
        HTTPException: 401 if token is invalid/expired or missing role
    """
    payload = verify_jwt(token)
    role = payload.get("role")

    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return role


def decode_token_from_cookie(cookie_value: Optional[str]) -> dict:
    """
    Decode a JWT from a cookie value.

    Args:
        cookie_value: Cookie value (may be None)

    Returns:
        Decoded payload dictionary

    Raises:
        HTTPException: 401 if cookie is missing or token is invalid
    """
    if not cookie_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication cookie",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_jwt(cookie_value)
