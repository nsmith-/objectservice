import pytest
from fastapi.testclient import TestClient

from ..shared.models.user import CurrentUser


def test_auth(client: TestClient, admin_token_headers) -> None:
    response = client.get("/auth/profile", headers=admin_token_headers)
    assert response.status_code == 200
    content = CurrentUser.model_validate_json(response.text)
    assert content.username == "test_admin"
    response = client.get("/auth/admin", headers=admin_token_headers)
    assert response.status_code == 200


def test_auth_secure(client: TestClient, user_token_headers) -> None:
    response = client.get("/auth/profile", headers=user_token_headers)
    assert response.status_code == 200
    content = CurrentUser.model_validate_json(response.text)
    assert content.username == "test_readonly"
    response = client.get("/auth/admin", headers=user_token_headers)
    assert response.status_code == 401


def test_auth_system(client: TestClient, system_token_headers) -> None:
    response = client.get("/auth/profile", headers=system_token_headers)
    assert response.status_code == 200
    content = CurrentUser.model_validate_json(response.text)
    assert content.name == "System User"
