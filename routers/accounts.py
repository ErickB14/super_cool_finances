from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.schemas import AccountCreate, AccountOut, BalanceOut
from db.models import Account, User
from core.security import get_current_user

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    body: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = Account(owner=body.owner, user_id=current_user.id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_uuid}/balance", response_model=BalanceOut)
def get_balance(
    account_uuid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = db.query(Account).filter(Account.uuid == account_uuid).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if current_user.role != "admin" and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this account")

    return BalanceOut(account_uuid=str(account.uuid), balance=account.balance)
