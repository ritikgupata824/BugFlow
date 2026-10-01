from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"webhook_{unique_id}"
    email = f"webhook_{unique_id}@example.com"
    password = "webhook123"

    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": "REPORTER",
        },
    )

    assert response.status_code in (200, 201), response.text

    return username, password


def get_test_token():
    username, password = create_test_user()

    response = client.post(
        "/auth/login",
        data={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"

    return data["access_token"]


def test_webhook_requires_authentication():
    response = client.post("/webhooks/test")

    assert response.status_code == 401


def test_webhook_test_endpoint():
    token = get_test_token()

    response = client.post(
        "/webhooks/test",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "status_code" in data
    assert "success" in data

    assert isinstance(data["status_code"], int)
    assert isinstance(data["success"], bool)

    assert data["status_code"] == 200
    assert data["success"] is True
