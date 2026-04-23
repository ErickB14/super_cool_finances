from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from db.models import Account, User
from schemas.schemas import LoginIn, RefreshIn, TokenOut
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_valid_refresh_token,
    revoke_refresh_token,
    store_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(user)
    refresh_token, expires_at = create_refresh_token(user)
    store_refresh_token(db, user.id, refresh_token, expires_at)

    return TokenOut(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_row = get_valid_refresh_token(db, body.refresh_token)
    if not token_row:
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

    user = db.query(User).filter(User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    revoke_refresh_token(db, body.refresh_token)

    access_token = create_access_token(user)
    new_refresh_token, expires_at = create_refresh_token(user)
    store_refresh_token(db, user.id, new_refresh_token, expires_at)

    return TokenOut(access_token=access_token, refresh_token=new_refresh_token)
