from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine

Base.metadata.create_all(bind=engine)


client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

def test_invalid_duplicate_merge():
    response = client.post(
        "/issues/8/merge/9999"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Duplicate issue not found"

def test_self_merge():
    response = client.post(
        "/issues/8/merge/8"
    )

    assert response.status_code == 400

    data = response.json()

    assert data["detail"] == "An issue cannot be merged with itself"

def test_valid_duplicate_merge():
    response = client.post(
        "/issues/8/merge/9"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["main_issue_id"] == 8
    assert data["duplicate_issue_id"] == 9
    assert data["duplicate_of_id"] == 8