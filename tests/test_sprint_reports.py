from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_developer():
    unique_id = uuid4().hex[:8]

    username = f"sprintdev_{unique_id}"
    email = f"sprintdev_{unique_id}@example.com"
    password = "sprint123"

    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": "DEVELOPER",
        },
    )

    assert response.status_code in (200, 201), response.text

    return username, password


def get_developer_token():
    username, password = create_developer()

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


def create_test_sprint(token):
    start_date = datetime.now() + timedelta(days=1)
    end_date = datetime.now() + timedelta(days=14)

    response = client.post(
        "/sprints",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": f"Report Sprint {uuid4().hex[:8]}",
            "description": "Sprint created for reporting tests",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "status": "PLANNED",
            "project_key": "BUGFLOW",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "id" in data
    assert data["status"] == "PLANNED"

    return data


def test_sprint_report():
    token = get_developer_token()

    sprint = create_test_sprint(token)

    response = client.get(
        "/reports/sprints",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "total_sprints" in data
    assert "sprints" in data

    assert isinstance(data["total_sprints"], int)
    assert data["total_sprints"] >= 1
    assert isinstance(data["sprints"], list)

    sprint_ids = [
        item["id"]
        for item in data["sprints"]
    ]

    assert sprint["id"] in sprint_ids

    for item in data["sprints"]:
        assert "id" in item
        assert "name" in item
        assert "status" in item
        assert "start_date" in item
        assert "end_date" in item


def test_sprint_issue_report():
    token = get_developer_token()

    sprint = create_test_sprint(token)

    sprint_id = sprint["id"]

    response = client.get(
        f"/reports/sprints/{sprint_id}/issues",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "sprint" in data
    assert "total_issues" in data
    assert "issues" in data

    assert data["sprint"]["id"] == sprint_id
    assert data["sprint"]["name"] == sprint["name"]
    assert data["sprint"]["status"] == "PLANNED"

    assert isinstance(data["total_issues"], int)
    assert data["total_issues"] == 0

    assert isinstance(data["issues"], list)
    assert len(data["issues"]) == 0


def test_sprint_summary_report():
    token = get_developer_token()

    sprint = create_test_sprint(token)

    sprint_id = sprint["id"]

    response = client.get(
        f"/reports/sprints/{sprint_id}/summary",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "sprint" in data
    assert "total_issues" in data
    assert "issues_by_status" in data

    assert data["sprint"]["id"] == sprint_id
    assert data["sprint"]["name"] == sprint["name"]
    assert data["sprint"]["status"] == "PLANNED"

    assert isinstance(data["total_issues"], int)
    assert data["total_issues"] == 0

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

    for status, count in data["issues_by_status"].items():
        assert isinstance(count, int)
        assert count >= 0


def test_sprint_issue_report_not_found():
    token = get_developer_token()

    response = client.get(
        "/reports/sprints/999999/issues",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sprint not found"


def test_sprint_summary_report_not_found():
    token = get_developer_token()

    response = client.get(
        "/reports/sprints/999999/summary",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sprint not found"


def test_sprint_report_requires_authentication():
    response = client.get("/reports/sprints")

    assert response.status_code == 401