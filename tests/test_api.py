import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

# Ensure tests run against local SQLite and a deterministic JWT secret.
os.environ["DATABASE_URL"] = "sqlite:///./test_super_cool_finances.db"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["AUTO_BOOTSTRAP_DB"] = "false"

from database import Base, SessionLocal, engine
from db.models import Account
from main import app
from database import get_db
from core.security import seed_default_users
from core.security import get_current_user


client = TestClient(app)


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)


@pytest.fixture(autouse=True)
def _db_isolation() -> None:
    reset_db()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


def login(username: str, password: str) -> dict:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


def auth_headers(username: str = "alice", password: str = "alice123") -> dict:
    tokens = login(username, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def create_account(owner: str = "Alice", headers: dict | None = None) -> dict:
    response = client.post("/accounts", json={"owner": owner}, headers=headers or auth_headers())
    assert response.status_code == 201
    return response.json()


def get_account_uuid(account_id: int) -> str:
    with SessionLocal() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        assert account is not None
        return str(account.uuid)


def get_account_balance(account_id: int) -> float:
    with SessionLocal() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        assert account is not None
        return float(account.balance)


class _FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self._first = first_result
        self._all = all_result if all_result is not None else []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all


class _FakeSession:
    def __init__(self, account=None, ledger_rows=None):
        self.account = account
        self.ledger_rows = ledger_rows if ledger_rows is not None else []

    def query(self, model):
        if model.__name__ == "Account":
            return _FakeQuery(first_result=self.account)
        return _FakeQuery(all_result=self.ledger_rows)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_and_refresh_success() -> None:
    login_response = client.post("/auth/login", json={"username": "alice", "password": "alice123"})
    assert login_response.status_code == 200

    tokens = login_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    refresh_response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 200

    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
    assert refreshed["refresh_token"] != tokens["refresh_token"]


def test_refresh_token_cannot_be_reused() -> None:
    tokens = login("alice", "alice123")

    first_refresh = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first_refresh.status_code == 200

    second_refresh = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert second_refresh.status_code == 401


def test_login_invalid_credentials_returns_401() -> None:
    response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401


def test_create_account_requires_auth() -> None:
    response = client.post("/accounts", json={"owner": "Alice"})
    assert response.status_code == 401


def test_create_account_success() -> None:
    response = client.post("/accounts", json={"owner": "Alice"}, headers=auth_headers())
    assert response.status_code == 201

    payload = response.json()
    assert payload["owner"] == "Alice"
    assert float(payload["balance"]) == 0.0


def test_create_account_owner_validation() -> None:
    response = client.post("/accounts", json={"owner": "  "}, headers=auth_headers())
    assert response.status_code == 422


def test_get_balance_success() -> None:
    account_uuid = uuid.uuid4()
    fake_account = SimpleNamespace(uuid=account_uuid, user_id=1, balance=Decimal("25.00"))
    fake_user = SimpleNamespace(id=1, role="customer")
    fake_db = _FakeSession(account=fake_account)

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = client.get(f"/accounts/{account_uuid}/balance")
    assert response.status_code == 200
    assert response.json()["account_uuid"] == str(account_uuid)
    assert float(response.json()["balance"]) == 25.0


def test_customer_cannot_read_other_user_balance() -> None:
    account_uuid = uuid.uuid4()
    fake_account = SimpleNamespace(uuid=account_uuid, user_id=10, balance=Decimal("50.00"))
    fake_user = SimpleNamespace(id=99, role="customer")
    fake_db = _FakeSession(account=fake_account)

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = client.get(f"/accounts/{account_uuid}/balance")
    assert response.status_code == 403


def test_admin_can_read_other_user_balance() -> None:
    account_uuid = uuid.uuid4()
    fake_account = SimpleNamespace(uuid=account_uuid, user_id=10, balance=Decimal("99.00"))
    fake_user = SimpleNamespace(id=1, role="admin")
    fake_db = _FakeSession(account=fake_account)

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = client.get(f"/accounts/{account_uuid}/balance")
    assert response.status_code == 200


def test_deposit_success_updates_balance() -> None:
    headers = auth_headers()
    account = create_account(headers=headers)
    account_id = account["id"]

    response = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 100.00, "description": "initial fund"},
        headers=headers,
    )
    assert response.status_code == 201
    payload = response.json()

    assert float(payload["amount_tx"]) == 100.0
    assert float(payload["disposable"]) == 100.0

    assert get_account_balance(account_id) == 100.0


def test_withdraw_success() -> None:
    headers = auth_headers()
    account = create_account(headers=headers)
    account_id = account["id"]

    client.post(f"/accounts/{account_id}/deposit", json={"amount": 100.00}, headers=headers)

    response = client.post(
        f"/accounts/{account_id}/withdraw",
        json={"amount": 40.00, "description": "atm"},
        headers=headers,
    )
    assert response.status_code == 201

    payload = response.json()
    assert float(payload["amount_tx"]) == 40.0
    assert float(payload["disposable"]) == 60.0


def test_withdraw_insufficient_funds() -> None:
    headers = auth_headers()
    account = create_account(headers=headers)
    account_id = account["id"]

    response = client.post(
        f"/accounts/{account_id}/withdraw",
        json={"amount": 10.00},
        headers=headers,
    )
    assert response.status_code == 422


def test_non_existing_account_returns_404() -> None:
    response = client.post(
        "/accounts/11111111-1111-1111-1111-111111111111/deposit",
        json={"amount": 10.00},
        headers=auth_headers(),
    )
    assert response.status_code == 404


def test_idempotency_key_on_deposit_prevents_duplicates() -> None:
    auth = auth_headers()
    account = create_account(headers=auth)
    account_id = account["id"]

    headers = {"idempotency-key": "deposit-001", **auth}

    first = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 50.00},
        headers=headers,
    )
    second = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 50.00},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    assert get_account_balance(account_id) == 50.0


def test_idempotency_key_on_withdraw_prevents_duplicates() -> None:
    auth = auth_headers()
    account = create_account(headers=auth)
    account_id = account["id"]

    client.post(f"/accounts/{account_id}/deposit", json={"amount": 100.00}, headers=auth)

    headers = {"idempotency-key": "withdraw-001", **auth}
    first = client.post(
        f"/accounts/{account_id}/withdraw",
        json={"amount": 20.00},
        headers=headers,
    )
    second = client.post(
        f"/accounts/{account_id}/withdraw",
        json={"amount": 20.00},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    assert get_account_balance(account_id) == 80.0


def test_customer_cannot_operate_other_user_account() -> None:
    alice_headers = auth_headers("alice", "alice123")
    bob_headers = auth_headers("bob", "bob123")

    account = create_account(owner="Alice Main", headers=alice_headers)
    account_id = account["id"]

    response = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 10.00},
        headers=bob_headers,
    )
    assert response.status_code == 403


def test_ledger_returns_account_history() -> None:
    account_uuid = uuid.uuid4()
    fake_account = SimpleNamespace(uuid=account_uuid, user_id=1, balance=Decimal("70.00"))
    fake_user = SimpleNamespace(id=1, role="customer")
    fake_rows = [
        SimpleNamespace(
            id=1,
            account_uuid=account_uuid,
            ttk_tracking_id="k1",
            disposable=Decimal("100.00"),
            type_tx="FUND",
            amount_tx=Decimal("100.00"),
            cdate=datetime.now(timezone.utc),
            status_tx="fund",
            description="seed",
        ),
        SimpleNamespace(
            id=2,
            account_uuid=account_uuid,
            ttk_tracking_id="k2",
            disposable=Decimal("70.00"),
            type_tx="CHARGE",
            amount_tx=Decimal("30.00"),
            cdate=datetime.now(timezone.utc),
            status_tx="settled",
            description="atm",
        ),
    ]
    fake_db = _FakeSession(account=fake_account, ledger_rows=fake_rows)

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = client.get(f"/accounts/{account_uuid}/ledger")
    assert response.status_code == 200

    records = response.json()
    assert len(records) == 2
    assert records[0]["type_tx"] == "FUND"
    assert records[1]["type_tx"] == "CHARGE"


def test_ledger_requires_valid_token() -> None:
    response = client.get(
        "/accounts/11111111-1111-1111-1111-111111111111/ledger",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
