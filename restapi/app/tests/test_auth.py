from fastapi.testclient import TestClient


def test_auth(client: TestClient, admin_token_headers) -> None:
    response = client.get("/auth/profile", headers=admin_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["username"] == "test_admin"


def test_auth_secure(client: TestClient, user_token_headers) -> None:
    response = client.get("/auth/profile", headers=user_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["username"] == "test_readonly"
