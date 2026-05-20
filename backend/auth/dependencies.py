"""
FastAPI dependency for JWT-based route protection.
Reads JWT from httpOnly cookie — never from Authorization header or request body.
"""

from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status

from .jwt_handler import COOKIE_NAME, verify_jwt


async def get_current_user(
    access_token: Optional[str] = Cookie(None),
) -> dict:
    """
    FastAPI dependency that extracts and verifies the JWT from httpOnly cookie.

    Inject into protected routes:
        @app.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"user": user}

    Args:
        access_token: JWT read from httpOnly cookie (injected by FastAPI)

    Returns:
        Full decoded token payload as dict:
        {
            "sub": "employee_id",
            "role": "finance",
            "department": "finance",
            "name": "Employee Name",
            "session_id": "uuid4",
            "exp": 1234567890
        }

    Raises:
        HTTPException: 401 if cookie is missing or token is invalid/expired
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication cookie",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_jwt(access_token)
    return payload
