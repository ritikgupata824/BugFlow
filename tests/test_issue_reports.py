from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"report_{unique_id}"
    email = f"report_{unique_id}@example.com"
    password = "report123"

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


def test_issue_report_without_filters():
    token = get_test_token()

    response = client.get(
        "/reports/issues",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_results" in data
    assert "filters" in data
    assert "issues" in data

    assert isinstance(data["total_results"], int)
    assert data["total_results"] >= 0

    assert data["filters"]["status"] is None
    assert data["filters"]["priority"] is None
    assert data["filters"]["severity"] is None

    assert isinstance(data["issues"], list)

    for issue in data["issues"]:
        assert "id" in issue
        assert "issue_key" in issue
        assert "title" in issue
        assert "status" in issue
        assert "priority" in issue
        assert "severity" in issue


def test_issue_report_status_filter():
    token = get_test_token()

    response = client.get(
        "/reports/issues?status=REPORTED",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["filters"]["status"] == "REPORTED"
    assert data["filters"]["priority"] is None
    assert data["filters"]["severity"] is None

    assert isinstance(data["issues"], list)

    for issue in data["issues"]:
        assert issue["status"] == "REPORTED"


def test_issue_report_priority_filter():
    token = get_test_token()

    response = client.get(
        "/reports/issues?priority=HIGH",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["filters"]["priority"] == "HIGH"
    assert data["filters"]["status"] is None
    assert data["filters"]["severity"] is None

    assert isinstance(data["issues"], list)

    for issue in data["issues"]:
        assert issue["priority"] == "HIGH"


def test_issue_report_severity_filter():
    token = get_test_token()

    response = client.get(
        "/reports/issues?severity=CRITICAL",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["filters"]["severity"] == "CRITICAL"
    assert data["filters"]["status"] is None
    assert data["filters"]["priority"] is None

    assert isinstance(data["issues"], list)

    for issue in data["issues"]:
        assert issue["severity"] == "CRITICAL"


def test_issue_report_multiple_filters():
    token = get_test_token()

    response = client.get(
        "/reports/issues?status=REPORTED&priority=HIGH&severity=CRITICAL",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["filters"]["status"] == "REPORTED"
    assert data["filters"]["priority"] == "HIGH"
    assert data["filters"]["severity"] == "CRITICAL"

    assert isinstance(data["issues"], list)

    for issue in data["issues"]:
        assert issue["status"] == "REPORTED"
        assert issue["priority"] == "HIGH"
        assert issue["severity"] == "CRITICAL"


def test_issue_report_requires_authentication():
    response = client.get("/reports/issues")

    assert response.status_code == 401