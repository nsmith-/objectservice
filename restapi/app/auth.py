import logging
import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security.oauth2 import SecurityScopes, get_authorization_scheme_param
from fastapi.security.open_id_connect_url import OpenIdConnect
from jose import JWTError, jwk, jwt
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class User(BaseModel):
    sub: str = Field(description="Subject (user unique ID)")
    username: str
    email: str | None = None
    name: str | None = None
    scopes: list[str] = []


_payload_example = {
    "exp": 1707336242,
    "iat": 1707335942,
    "jti": "0593dba4-35ac-4e23-891a-a40365ddb59c",
    "iss": "http://keycloak:8080/auth/realms/test",
    "aud": "account",
    "sub": "1172bce4-538b-4e63-ae43-bc92453911bc",
    "typ": "Bearer",
    "azp": "restapi",
    "session_state": "d4f3dcd8-f839-462d-9aa2-dfa007cfaee0",
    "acr": "1",
    "allowed-origins": ["http://localhost:8888"],
    "realm_access": {"roles": ["readonly", "offline_access", "uma_authorization"]},
    "resource_access": {
        "account": {"roles": ["manage-account", "manage-account-links", "view-profile"]}
    },
    "scope": "openid profile email",
    "email_verified": False,
    "name": "Book Worm",
    "preferred_username": "test_readonly",
    "given_name": "Book",
    "family_name": "Worm",
    "email": "readonly@test.com",
}


class OIDCAccountProvider(OpenIdConnect):
    def __init__(self, provider_url: str):
        super().__init__(
            openIdConnectUrl=provider_url + "/.well-known/openid-configuration",
            scheme_name=provider_url,
            description="OpenID-connect provider",
            auto_error=False,
        )
        self._key = None

    async def setup(self):
        async with httpx.AsyncClient() as client:
            config = (await client.get(self.model.openIdConnectUrl)).json()
            key_data = (await client.get(config["jwks_uri"])).json()
        self._issuer: str = config["issuer"]
        self._key = {key["kid"]: jwk.construct(key) for key in key_data["keys"]}

    async def __call__(self, request: Request) -> User | None:
        if not self._key:
            raise RuntimeError(
                "Provider not initialized! Make sure to call setup() in app lifespan"
            )
        authorization = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            return None
        try:
            payload = jwt.decode(
                token,
                key=self._key,
                audience="account",
                issuer=self._issuer,
            )
            if payload.get("azp") != "restapi":
                return None
            print(payload)
            scopes = payload.get("scopes", [])
            # add also keycloak realm roles
            if realm := payload.get("realm_access"):
                scopes += realm["roles"]
            return User(
                sub=payload.get("sub"),
                username=payload.get("preferred_username"),
                email=payload.get("email"),
                name=payload.get("name"),
                scopes=scopes,
            )
        except (JWTError, ValidationError) as ex:
            logger.warning(str(ex))
            return None


account_provider = OIDCAccountProvider(os.environ["OIDC_PROVIDER"])


async def authorized_user(
    security_scopes: SecurityScopes, user: Annotated[User, Depends(account_provider)]
):
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    for scope in security_scopes.scopes:
        if scope not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.get("/profile", response_model=User)
async def read_profile(user: Annotated[User, Depends(authorized_user)]):
    return user


@router.get("/secured")
async def read_own_items(
    current_user: Annotated[User, Security(authorized_user, scopes=["blah"])]
):
    return "ok"
