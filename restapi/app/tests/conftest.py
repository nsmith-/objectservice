import os
from typing import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from ..main import app

OAUTH_CLIENT_ID = os.environ["OAUTH_CLIENT_ID"]
OIDC_PROVIDER = os.environ["OIDC_PROVIDER"]
SYSTEM_USERNAME = os.environ["SYSTEM_USERNAME"]
SYSTEM_PASSWORD = os.environ["SYSTEM_PASSWORD"]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def auth_flow(
    username: str,
    password: str,
    *,
    scopes: list[str] = [],
    auth_client: httpx.Client | None = None,
) -> dict[str, str]:
    login_data = {
        "grant_type": "password",
        "scope": " ".join(scopes),
        "username": username,
        "password": password,
        "client_id": OAUTH_CLIENT_ID,
    }
    if auth_client:
        response = auth_client.post("auth/token", data=login_data)
    else:
        response = httpx.post(
            f"{OIDC_PROVIDER}/protocol/openid-connect/token", data=login_data
        )
    tokens = response.json()
    a_token = tokens.get("access_token")
    if not a_token:
        print(tokens)
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


@pytest.fixture(scope="module")
def admin_token_headers() -> dict[str, str]:
    return auth_flow(username="test_admin", password="admin", scopes=["openid"])


@pytest.fixture(scope="module")
def user_token_headers() -> dict[str, str]:
    return auth_flow(username="test_readonly", password="bookworm", scopes=["openid"])


@pytest.fixture(scope="module")
def system_token_headers(client: TestClient) -> dict[str, str]:
    return auth_flow(
        username=SYSTEM_USERNAME, password=SYSTEM_PASSWORD, auth_client=client
    )
