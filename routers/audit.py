from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.schemas import MovementOut, BalanceHstOut
from db.models import Account, BalanceHst, User
from core.security import get_current_user

router = APIRouter(prefix="/accounts", tags=["Audit"])



@router.get("/{account_uuid}/ledger", response_model=list[BalanceHstOut])
def get_balance_history(
    account_uuid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = db.query(Account).filter(Account.uuid == account_uuid).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if current_user.role != "admin" and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this account")

    records = (
        db.query(BalanceHst)
        .filter(BalanceHst.account_uuid == account.uuid)
        .order_by(BalanceHst.cdate)
        .all()
    )
    return records
