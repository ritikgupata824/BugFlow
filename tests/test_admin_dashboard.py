from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_user(role="REPORTER"):
    unique_id = uuid4().hex[:8]

    username = f"dashboard_{unique_id}"
    email = f"dashboard_{unique_id}@example.com"
    password = "dashboard123"

    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": role,
        },
    )

    assert response.status_code in (200, 201), response.text

    return username, password


def get_test_token(role="REPORTER"):
    username, password = create_test_user(role)

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


def test_admin_dashboard_access():
    token = get_test_token("ADMIN")

    response = client.get(
        "/admin/dashboard",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_issues" in data
    assert "total_users" in data
    assert "total_sprints" in data

    assert isinstance(data["total_issues"], int)
    assert isinstance(data["total_users"], int)
    assert isinstance(data["total_sprints"], int)

    assert data["total_issues"] >= 0
    assert data["total_users"] >= 0
    assert data["total_sprints"] >= 0


def test_reporter_cannot_access_admin_dashboard():
    token = get_test_token("REPORTER")

    response = client.get(
        "/admin/dashboard",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403, response.text