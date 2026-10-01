from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"severity_{unique_id}"
    email = f"severity_{unique_id}@example.com"
    password = "severity123"

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


def test_severity_analytics_api():
    token = get_test_token()

    response = client.get(
        "/analytics/severity",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_issues" in data
    assert "issues_by_severity" in data

    assert isinstance(data["total_issues"], int)
    assert data["total_issues"] >= 0

    assert isinstance(data["issues_by_severity"], dict)

    expected_severities = {
        "MINOR",
        "MAJOR",
        "CRITICAL",
        "BLOCKER",
    }

    assert expected_severities.issubset(
        set(data["issues_by_severity"].keys())
    )

    for severity in expected_severities:
        assert isinstance(
            data["issues_by_severity"][severity],
            int
        )

        assert data["issues_by_severity"][severity] >= 0