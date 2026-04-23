from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session
from database import get_db
from schemas.schemas import DepositIn, WithdrawIn, BalanceHstOut
from db.models import BalanceHst, User
from core.security import get_current_user
from core.validators import get_account_or_404, validate_withdraw

router = APIRouter(prefix="/accounts", tags=["Movements"])


@router.post("/{account_uuid}/deposit", response_model=BalanceHstOut, status_code=201)
def deposit(
    account_uuid: str,
    body: DepositIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="idempotency-key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = get_account_or_404(account_uuid, db)
    if current_user.role != "admin" and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this account")

    amount = Decimal(str(body.amount))

    if idempotency_key:
        existing = (
            db.query(BalanceHst)
            .filter(
                BalanceHst.account_uuid == account.uuid,
                BalanceHst.ttk_tracking_id == idempotency_key,
                BalanceHst.type_tx == "FUND",
            )
            .first()
        )
        if existing:
            response.status_code = 200
            return existing

    account.balance += amount

    hst = BalanceHst(
        account_uuid=account.uuid,
        ttk_tracking_id=idempotency_key,
        disposable=account.balance,
        type_tx="FUND",
        amount_tx=amount,
        status_tx="fund",
        description=body.description,
    )
    db.add(hst)

    db.commit()
    db.refresh(hst)
    return hst


@router.post("/{account_uuid}/withdraw", response_model=BalanceHstOut, status_code=201)
def withdraw(
    account_uuid: str,
    body: WithdrawIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="idempotency-key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = get_account_or_404(account_uuid, db)
    if current_user.role != "admin" and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this account")

    amount = Decimal(str(body.amount))

    if idempotency_key:
        existing = (
            db.query(BalanceHst)
            .filter(
                BalanceHst.account_uuid == account.uuid,
                BalanceHst.ttk_tracking_id == idempotency_key,
                BalanceHst.type_tx == "CHARGE",
            )
            .first()
        )
        if existing:
            response.status_code = 200
            return existing

    validate_withdraw(account, amount)

    account.balance -= amount

    hst = BalanceHst(
        account_uuid=account.uuid,
        ttk_tracking_id=idempotency_key,
        disposable=account.balance,
        type_tx="CHARGE",
        amount_tx=amount,
        status_tx="settled",
        description=body.description,
    )
    db.add(hst)

    db.commit()
    db.refresh(hst)
    return hst
