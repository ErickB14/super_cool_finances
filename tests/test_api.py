import os

# Ensure tests use local SQLite instead of external DB.
os.environ["DATABASE_URL"] = "sqlite:///./test_testefex.db"

from fastapi.testclient import TestClient

from database import Base, SessionLocal, engine
from main import app
from core.security import seed_default_users


client = TestClient(app)


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)


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


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_account_success() -> None:
    reset_db()
    response = client.post("/accounts", json={"owner": "Alice"}, headers=auth_headers())

    assert response.status_code == 201
    payload = response.json()
    assert payload["owner"] == "Alice"
    assert float(payload["balance"]) == 0.0


def test_create_account_owner_validation() -> None:
    reset_db()
    response = client.post("/accounts", json={"owner": "  "}, headers=auth_headers())

    assert response.status_code == 422


def test_login_and_refresh_success() -> None:
    reset_db()
    login_response = client.post("/auth/login", json={"username": "alice", "password": "alice123"})
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    refresh_response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"] != tokens["refresh_token"]


def test_deposit_success() -> None:
    reset_db()
    headers = auth_headers()
    account = create_account(headers=headers)

    response = client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": 100.00, "description": "initial fund"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert float(payload["amount_tx"]) == 100.0
    assert float(payload["disposable"]) == 100.0


def test_deposit_success_with_uuid_path() -> None:
    reset_db()
    headers = auth_headers()
    account = create_account(headers=headers)

    response = client.post(
        f"/accounts/{account['uuid']}/deposit",
        json={"amount": 100.00, "description": "initial fund"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert float(payload["amount_tx"]) == 100.0
    assert float(payload["disposable"]) == 100.0


def test_withdraw_success() -> None:
    reset_db()
    headers = auth_headers()
    account = create_account(headers=headers)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": 100.00}, headers=headers)

    response = client.post(
        f"/accounts/{account['id']}/withdraw",
        json={"amount": 40.00, "description": "atm"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert float(payload["amount_tx"]) == 40.0
    assert float(payload["disposable"]) == 60.0


def test_withdraw_insufficient_funds() -> None:
    reset_db()
    headers = auth_headers()
    account = create_account(headers=headers)

    response = client.post(
        f"/accounts/{account['id']}/withdraw",
        json={"amount": 10.00},
        headers=headers,
    )

    assert response.status_code == 422


def test_non_existing_account_returns_404() -> None:
    reset_db()
    response = client.post("/accounts/999/deposit", json={"amount": 10.00}, headers=auth_headers())
    assert response.status_code == 404


def test_idempotency_key_on_deposit_prevents_duplicates() -> None:
    reset_db()
    auth = auth_headers()
    account = create_account(headers=auth)
    headers = {"idempotency-key": "deposit-001", **auth}

    first = client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": 50.00},
        headers=headers,
    )
    second = client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": 50.00},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    balance = client.get(f"/accounts/{first.json()['account_uuid']}/balance", headers=auth)
    assert balance.status_code == 200
    assert float(balance.json()["balance"]) == 50.0


def test_idempotency_key_on_withdraw_prevents_duplicates() -> None:
    reset_db()
    auth = auth_headers()
    account = create_account(headers=auth)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": 100.00}, headers=auth)

    headers = {"idempotency-key": "withdraw-001", **auth}
    first = client.post(
        f"/accounts/{account['id']}/withdraw",
        json={"amount": 20.00},
        headers=headers,
    )
    second = client.post(
        f"/accounts/{account['id']}/withdraw",
        json={"amount": 20.00},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    balance = client.get(f"/accounts/{first.json()['account_uuid']}/balance", headers=auth)
    assert balance.status_code == 200
    assert float(balance.json()["balance"]) == 80.0


def test_customer_cannot_operate_other_user_account() -> None:
    reset_db()
    alice_headers = auth_headers("alice", "alice123")
    bob_headers = auth_headers("bob", "bob123")

    account = create_account(owner="Alice Main", headers=alice_headers)
    response = client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": 10.00},
        headers=bob_headers,
    )

    assert response.status_code == 403
