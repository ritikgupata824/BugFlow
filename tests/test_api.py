from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import (
    User,
    Issue,
    IssueType,
    Severity,
    BusinessImpact,
    Priority,
    IssueStatus,
)


Base.metadata.create_all(bind=engine)

client = TestClient(app)


def get_test_token():
    username = "pytest_user"
    password = "pytest_password_123"

    register_response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": "pytest@example.com",
            "password": password,
            "role": "REPORTER"
        }
    )

    assert register_response.status_code in (200, 400)

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password
        }
    )

    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def get_test_user_id():
    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.username == "pytest_user"
        ).first()

        assert user is not None

        return user.id

    finally:
        db.close()


def test_root():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"


def test_invalid_duplicate_merge():
    response = client.post(
        "/issues/9999/merge/9998"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Main issue not found"


def test_self_merge():
    response = client.post(
        "/issues/9999/merge/9999"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Main issue not found"


def test_valid_duplicate_merge():
    """
    Test duplicate issue merging directly through the merge API.

    Issues are created directly in the test database so this test
    does not depend on the /issues creation endpoint.
    """

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.username == "pytest_user"
        ).first()

        if user is None:
            user = User(
                username="pytest_user",
                email="pytest@example.com",
                password="pytest_password_123",
                role="REPORTER",
                is_active=True
            )

            db.add(user)
            db.commit()
            db.refresh(user)

        main_issue = Issue(
            issue_key="TEST-MAIN-MERGE",
            issue_type=IssueType.BUG,
            title="CI Main Test Issue",
            description="Main issue created for duplicate merge testing",
            reproduction_steps="Run automated tests",
            severity=Severity.MAJOR,
            business_impact=BusinessImpact.HIGH,
            priority=Priority.HIGH,
            status=IssueStatus.REPORTED,
            affected_module="Testing",
            environment="CI",
            screenshot_url=None,
            project_key="TEST",
            reporter_id=user.id,
            assignee_id=None,
            sprint_id=None
        )

        duplicate_issue = Issue(
            issue_key="TEST-DUPLICATE-MERGE",
            issue_type=IssueType.BUG,
            title="CI Duplicate Test Issue",
            description="Duplicate issue created for duplicate merge testing",
            reproduction_steps="Run automated tests",
            severity=Severity.MAJOR,
            business_impact=BusinessImpact.HIGH,
            priority=Priority.HIGH,
            status=IssueStatus.REPORTED,
            affected_module="Testing",
            environment="CI",
            screenshot_url=None,
            project_key="TEST",
            reporter_id=user.id,
            assignee_id=None,
            sprint_id=None
        )

        db.add(main_issue)
        db.add(duplicate_issue)

        db.commit()

        db.refresh(main_issue)
        db.refresh(duplicate_issue)

        main_id = main_issue.id
        duplicate_id = duplicate_issue.id

    finally:
        db.close()

    response = client.post(
        f"/issues/{main_id}/merge/{duplicate_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["main_issue_id"] == main_id
    assert data["duplicate_issue_id"] == duplicate_id
    assert data["duplicate_of_id"] == main_id