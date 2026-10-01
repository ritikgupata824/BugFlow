from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"summary_{unique_id}"
    email = f"summary_{unique_id}@example.com"
    password = "summary123"

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


def test_summary_report_api():
    token = get_test_token()

    response = client.get(
        "/reports/summary",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_issues" in data
    assert "open_issues" in data
    assert "resolved_issues" in data
    assert "closed_issues" in data

    assert isinstance(data["total_issues"], int)
    assert isinstance(data["open_issues"], int)
    assert isinstance(data["resolved_issues"], int)
    assert isinstance(data["closed_issues"], int)

    assert data["total_issues"] >= 0
    assert data["open_issues"] >= 0
    assert data["resolved_issues"] >= 0
    assert data["closed_issues"] >= 0

    assert (
        data["open_issues"]
        + data["resolved_issues"]
        + data["closed_issues"]
        <= data["total_issues"]
    )