import logging
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security.oauth2 import SecurityScopes, get_authorization_scheme_param
from fastapi.security.open_id_connect_url import OpenIdConnect
from jose import JWTError, jwt
from pydantic import BaseModel, Field, ValidationError

from . import jwtutil

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
    _data: jwtutil.OIDCProviderData | None

    def __init__(self, oidc_provider_url: str):
        super().__init__(
            openIdConnectUrl=oidc_provider_url + jwtutil.OIDC_WELLKNOWN,
            scheme_name=oidc_provider_url,
            description="OpenID-connect provider",
            auto_error=False,
        )
        self._data = None

    async def setup(self):
        self._data = await jwtutil.fetch_OIDCProviderData(self.model.openIdConnectUrl)

    async def __call__(self, request: Request) -> User | None:  # type: ignore[override]
        if not self._data:
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
                key=self._data.keys,
                audience="account",
                issuer=self._data.issuer,
            )
            if payload.get("azp") != "restapi":
                return None
            logger.debug(payload)
            scopes = payload.get("scopes", [])
            # add also keycloak realm roles
            if realm := payload.get("realm_access"):
                scopes += realm["roles"]
            return User(
                sub=payload["sub"],
                username=payload["preferred_username"],
                email=payload.get("email"),
                name=payload.get("name"),
                scopes=scopes,
            )
        except (JWTError, ValidationError, KeyError) as ex:
            logger.warning(str(ex))
            return None


account_provider = OIDCAccountProvider(os.environ["OIDC_PROVIDER"])


async def authorized_user(
    security_scopes: SecurityScopes, user: Annotated[User, Depends(account_provider)]
) -> User:
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


AuthorizedUser = Annotated[User, Depends(authorized_user)]
Administrator = Annotated[User, Security(authorized_user, scopes=["admin"])]

router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@router.get("/profile", response_model=User)
async def read_profile(user: AuthorizedUser):
    return user


@router.get("/admin")
async def read_admin(user: Administrator):
    return user
