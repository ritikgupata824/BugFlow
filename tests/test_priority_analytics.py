from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"priority_{unique_id}"
    email = f"priority_{unique_id}@example.com"
    password = "priority123"

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


def test_priority_analytics_api():
    token = get_test_token()

    response = client.get(
        "/analytics/priority",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_issues" in data
    assert "issues_by_priority" in data

    assert isinstance(data["total_issues"], int)
    assert data["total_issues"] >= 0

    assert isinstance(data["issues_by_priority"], dict)

    expected_priorities = {
        "LOW",
        "MEDIUM",
        "HIGH",
        "URGENT",
    }

    assert expected_priorities.issubset(
        set(data["issues_by_priority"].keys())
    )

    for priority in expected_priorities:
        assert isinstance(
            data["issues_by_priority"][priority],
            int
        )

        assert data["issues_by_priority"][priority] >= 0