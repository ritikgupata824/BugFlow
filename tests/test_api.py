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


def create_test_user(role="REPORTER"):
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


def get_user_id_from_token(token):
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
        description="Main issue created for automated testing",
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


def test_create_issue_api():
    token = get_test_token()

    reporter_id = get_user_id_from_token(token)

    response = client.post(
        "/issues",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "issue_type": "BUG",
            "title": "Automated API test issue",
            "description": "Testing issue creation API",
            "reproduction_steps": "Run pytest",
            "severity": "MAJOR",
            "business_impact": "HIGH",
            "priority": "HIGH",
            "affected_module": "API",
            "environment": "TEST",
            "screenshot_url": None,
            "project_key": "PYTEST",
            "reporter_id": reporter_id,
            "assignee_id": None,
            "sprint_id": None,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["title"] == "Automated API test issue"
    assert data["issue_type"] == "BUG"
    assert data["severity"] == "MAJOR"
    assert data["business_impact"] == "HIGH"
    assert data["priority"] == "HIGH"
    assert data["project_key"] == "PYTEST"


def test_get_single_issue_api():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_user_id_from_token(token)

        issue = create_unique_issue(
            db,
            f"TEST-GET-{uuid4().hex[:8]}",
            "Get Issue API Test",
            reporter_id,
        )

        issue_id = issue.id

    finally:
        db.close()

    response = client.get(
        f"/issues/{issue_id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == issue_id
    assert data["title"] == "Get Issue API Test"


def test_update_issue_api():
    # Issue update API requires ADMIN or DEVELOPER.
    token = get_test_token("DEVELOPER")

    db = SessionLocal()

    try:
        reporter_id = get_user_id_from_token(token)

        issue = create_unique_issue(
            db,
            f"TEST-UPDATE-{uuid4().hex[:8]}",
            "Original Issue Title",
            reporter_id,
        )

        issue_id = issue.id

    finally:
        db.close()

    response = client.put(
        f"/issues/{issue_id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "title": "Updated Issue Title",
            "description": "Updated issue description",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == issue_id
    assert data["title"] == "Updated Issue Title"
    assert data["description"] == "Updated issue description"


def test_duplicate_detection():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_user_id_from_token(token)

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

    data = response.json()

    assert data["issue_id"] == main_issue_id
    assert "duplicates" in data


def test_valid_duplicate_merge():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_user_id_from_token(token)

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


def test_invalid_duplicate_merge_returns_404():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_user_id_from_token(token)

        main_issue = create_unique_issue(
            db,
            f"TEST-MAIN-404-{uuid4().hex[:8]}",
            "Main Issue 404 Test",
            reporter_id,
        )

        main_issue_id = main_issue.id

    finally:
        db.close()

    response = client.post(
        f"/issues/{main_issue_id}/merge/999999",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 404


def test_self_duplicate_merge_returns_400():
    token = get_test_token()

    db = SessionLocal()

    try:
        reporter_id = get_user_id_from_token(token)

        issue = create_unique_issue(
            db,
            f"TEST-SELF-MERGE-{uuid4().hex[:8]}",
            "Self Merge Test",
            reporter_id,
        )

        issue_id = issue.id

    finally:
        db.close()

    response = client.post(
        f"/issues/{issue_id}/merge/{issue_id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 400