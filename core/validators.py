from decimal import Decimal
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from db.models import Account


def get_account_or_404(account_ref: str, db: Session) -> Account:
    # UUID is the canonical external identifier. Keep numeric ID support for compatibility.
    account = None

    try:
        account_uuid = uuid.UUID(account_ref)
        account = (
            db.query(Account)
            .filter(Account.uuid == account_uuid)
            .with_for_update()
            .first()
        )
    except ValueError:
        if account_ref.isdigit():
            account = (
                db.query(Account)
                .filter(Account.id == int(account_ref))
                .with_for_update()
                .first()
            )

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def validate_withdraw(account: Account, amount: Decimal) -> None:
    if account.balance <= 0:
        raise HTTPException(status_code=422, detail="Account has no available balance")

    if amount > account.balance:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient balance. Available: {account.balance}",
        )
