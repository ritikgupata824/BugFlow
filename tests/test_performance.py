from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"perf_{unique_id}"
    email = f"perf_{unique_id}@example.com"
    password = "perf123"

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


def test_reports_summary_response_time():
    token = get_test_token()

    start_time = perf_counter()

    response = client.get(
        "/reports/summary",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    elapsed_ms = (
        perf_counter() - start_time
    ) * 1000

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_issues" in data
    assert "open_issues" in data
    assert "resolved_issues" in data
    assert "closed_issues" in data

    assert elapsed_ms < 300, (
        f"API response took {elapsed_ms:.2f} ms"
    )
