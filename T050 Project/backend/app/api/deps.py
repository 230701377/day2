from typing import Generator, Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_token
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        # allow header override
        token = request.headers.get("x-access-token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        token = request.headers.get("x-access-token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id:
            return db.query(User).filter(User.id == user_id).first()
    except Exception:
        pass
    return None


def require_role(*roles: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Requires one of: {', '.join(roles)}")
        return user
    return dep


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""
