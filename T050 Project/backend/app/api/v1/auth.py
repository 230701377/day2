from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import get_current_user, require_role
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token
)
from app.models.models import User, AuditLog
from app.schemas.schemas import (
    UserCreate, UserUpdate, UserOut, LoginRequest, TokenOut,
)
from app.services.audit.chain import append as audit_append

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    access = create_access_token(user.id, extra={"role": user.role})
    refresh = create_refresh_token(user.id)
    audit_append(db, actor=user, action="auth.login", resource_type="user",
                 resource_id=str(user.id), payload={"ip": "n/a"})
    return TokenOut(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenOut)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access = create_access_token(user.id, extra={"role": user.role})
    refresh = create_refresh_token(user.id)
    return TokenOut(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/users", response_model=UserOut, dependencies=[Depends(require_role("admin"))])
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                actor: User = Depends(get_current_user)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        department=payload.department,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    audit_append(db, actor=actor, action="user.create", resource_type="user",
                 resource_id=str(user.id), payload={"email": user.email, "role": user.role})
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role("admin", "legal",
                                                                                  "compliance", "executive",
                                                                                  "manager", "finance"))):
    return db.query(User).order_by(User.full_name.asc()).all()


@router.patch("/users/{user_id}", response_model=UserOut,
              dependencies=[Depends(require_role("admin"))])
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db),
                actor: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.flush()
    audit_append(db, actor=actor, action="user.update", resource_type="user",
                 resource_id=str(user.id), payload=payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(user)
    return user
