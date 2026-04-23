from pydantic import BaseModel, Field, field_serializer, field_validator
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from db.models import MovementType


# ---------- Account ----------

class AccountCreate(BaseModel):
    owner: str = Field(min_length=3, description="Owner name must be at least 3 characters")

    @field_validator("owner")
    @classmethod
    def validate_owner_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Owner must contain at least 3 non-whitespace characters")
        return cleaned


class AccountOut(BaseModel):
    id: int
    owner: str
    balance: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    account_uuid: str
    balance: Decimal

    @field_serializer("balance")
    def serialize_balance_as_number(self, value: Decimal) -> float:
        return float(value)


# ---------- Movements ----------

class DepositIn(BaseModel):
    amount: float = Field(gt=0, multiple_of=0.01, description="Amount must be positive and up to 2 decimal places")
    description: str | None = None


class WithdrawIn(BaseModel):
    amount: float = Field(gt=0, multiple_of=0.01, description="Amount must be positive and up to 2 decimal places")
    description: str | None = None


class MovementOut(BaseModel):
    id: int
    account_id: int
    type: MovementType
    amount: Decimal
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Balance History ----------

class BalanceHstOut(BaseModel):
    id: int
    account_uuid: UUID
    ttk_tracking_id: str | None
    disposable: Decimal
    type_tx: str
    amount_tx: Decimal
    cdate: datetime
    status_tx: str
    description: str | None

    model_config = {"from_attributes": True}

    @field_serializer("disposable", "amount_tx")
    def serialize_money_as_number(self, value: Decimal) -> float:
        return float(value)


# ---------- Transfer ----------

class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal
    description: str | None = None


class TransferOut(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal
    description: str | None


# ---------- Auth ----------

class LoginIn(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 bytes")
        return value


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
