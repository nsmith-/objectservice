import os
from typing import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from ..main import app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def auth_flow(username: str, password: str) -> dict[str, str]:
    login_data = {
        "grant_type": "password",
        "scope": "openid",
        "username": username,
        "password": password,
    }
    provider_url = os.environ["OIDC_PROVIDER"]
    auth = httpx.BasicAuth(
        username=os.environ["OAUTH_CLIENT_ID"],
        password=os.environ["OAUTH_CLIENT_SECRET"],
    )
    r = httpx.post(
        f"{provider_url}/protocol/openid-connect/token", auth=auth, data=login_data
    )
    print(r.status_code)
    print(r.json())
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


@pytest.fixture(scope="module")
def admin_token_headers(client: TestClient) -> dict[str, str]:
    return auth_flow(username="test_admin", password="admin")


@pytest.fixture(scope="module")
def user_token_headers(client: TestClient) -> dict[str, str]:
    return auth_flow(username="test_readonly", password="bookworm")
