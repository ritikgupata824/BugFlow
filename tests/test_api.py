from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import (
    User,
    Issue,
    IssueType,
    Severity,
    BusinessImpact,
    Priority,
)


client = TestClient(app)


def create_test_user():
    unique_id = uuid4().hex[:8]

    username = f"pytest_{unique_id}"
    email = f"pytest_{unique_id}@example.com"
    password = "pytest123"

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

    return data["access_token"]


def create_unique_issue(
    db,
    issue_key,
    title,
    reporter_id,
):
    existing_issue = (
        db.query(Issue)
        .filter(Issue.issue_key == issue_key)
        .first()
    )

    if existing_issue:
        db.delete(existing_issue)
        db.commit()

    issue = Issue(
        issue_key=issue_key,
        issue_type=IssueType.BUG,
        title=title,
        description="Main issue created for duplicate merge testing",
        reproduction_steps="Run automated tests",
        severity=Severity.MAJOR,
        business_impact=BusinessImpact.HIGH,
        priority=Priority.HIGH,
        affected_module="Testing",
        environment="CI",
        project_key="TEST",
        reporter_id=reporter_id,
    )

    db.add(issue)
    db.commit()
    db.refresh(issue)

    return issue


def get_reporter_id_from_token(token):
    response = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    if response.status_code == 200:
        return response.json()["id"]

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .order_by(User.id.desc())
            .first()
        )

        assert user is not None

        return user.id

    finally:
        db.close()


def test_root():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"


def test_register_and_login():
    username, password = create_test_user()

    login_response = client.post(
        "/auth/login",
        data={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 200, login_response.text

    token_data = login_response.json()

    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_protected_issues_endpoint():
    token = get_test_token()

    response = client.get(
        "/issues",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text


def test_duplicate_detection():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_reporter_id_from_token(token)

        main_issue = create_unique_issue(
            db,
            f"TEST-DUP-MAIN-{uuid4().hex[:8]}",
            "Login button not working",
            reporter_id,
        )

        create_unique_issue(
            db,
            f"TEST-DUP-SECOND-{uuid4().hex[:8]}",
            "Login button not working after clicking",
            reporter_id,
        )

        main_issue_id = main_issue.id

    finally:
        db.close()

    response = client.get(
        f"/issues/{main_issue_id}/duplicates",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text


def test_valid_duplicate_merge():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_reporter_id_from_token(token)

        main_issue = create_unique_issue(
            db,
            f"TEST-MAIN-MERGE-{uuid4().hex[:8]}",
            "CI Main Test Issue",
            reporter_id,
        )

        duplicate_issue = create_unique_issue(
            db,
            f"TEST-DUP-MERGE-{uuid4().hex[:8]}",
            "CI Duplicate Test Issue",
            reporter_id,
        )

        main_issue_id = main_issue.id
        duplicate_issue_id = duplicate_issue.id

    finally:
        db.close()

    response = client.post(
        f"/issues/{main_issue_id}/merge/{duplicate_issue_id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["duplicate_of_id"] == main_issue_id