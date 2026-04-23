import enum
import uuid as _uuid
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy import UUID
from sqlalchemy.sql import func
from database import Base


class MovementType(str, enum.Enum):
    charge = "charge"
    fund   = "fund"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    uuid = Column(UUID(as_uuid=True), default=_uuid.uuid4, unique=True, nullable=False, index=True)
    owner = Column(String, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="customer")
    created_at = Column(DateTime, server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class BalanceHst(Base):
    __tablename__ = "balance_hst"

    id           = Column(Integer, primary_key=True, index=True)
    account_uuid = Column(UUID(as_uuid=True), ForeignKey("accounts.uuid"), nullable=False, index=True)
    ttk_tracking_id = Column(String, nullable=True)
    disposable   = Column(Numeric(12, 2), nullable=False)
    type_tx      = Column(String, nullable=False)
    amount_tx    = Column(Numeric(12, 2), nullable=False)
    cdate        = Column(DateTime, server_default=func.now(), nullable=False)
    status_tx    = Column(String, nullable=False)
    description  = Column(String, nullable=True)

