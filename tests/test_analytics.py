from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"analytics_{unique_id}"
    email = f"analytics_{unique_id}@example.com"
    password = "analytics123"

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


def test_issue_analytics_api():
    token = get_test_token()

    response = client.get(
        "/analytics/issues",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_issues" in data
    assert "issues_by_status" in data

    assert isinstance(data["total_issues"], int)
    assert data["total_issues"] >= 0

    assert isinstance(data["issues_by_status"], dict)

    expected_statuses = {
        "REPORTED",
        "TRIAGED",
        "ASSIGNED",
        "IN_DEVELOPMENT",
        "IN_REVIEW",
        "IN_TESTING",
        "RESOLVED",
        "CLOSED",
        "REOPENED",
    }

    assert expected_statuses.issubset(
        set(data["issues_by_status"].keys())
    )