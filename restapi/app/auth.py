import datetime
import hashlib
import logging
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.openapi.models import OAuth2
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security.oauth2 import SecurityScopes, get_authorization_scheme_param
from fastapi.security.open_id_connect_url import OpenIdConnect
from jose import JWTError, jwk, jwt
from pydantic import BaseModel, ValidationError, field_serializer

from .shared import jwtutil
from .shared.models.user import CurrentUser

logger = logging.getLogger(__name__)


class Token(BaseModel):
    access_token: str
    token_type: Literal["Bearer"]


class TokenData(BaseModel):
    """JWT token info

    Fields: https://www.iana.org/assignments/jwt/jwt.xhtml
    """

    exp: datetime.datetime
    iat: datetime.datetime
    iss: str
    aud: str
    sub: str
    typ: Literal["Bearer"]
    azp: str
    scope: str
    email: str
    name: str
    preferred_username: str
    given_name: str
    family_name: str

    @property
    def scopes(self) -> list[str]:
        return self.scope.split(" ")

    @field_serializer("exp", "iat")
    def serialize_datetime(self, obj: datetime.datetime) -> int:
        return int(obj.timestamp())


OAUTH_CLIENT_ID = os.environ["OAUTH_CLIENT_ID"]
OIDC_PROVIDER = os.environ["OIDC_PROVIDER"]
ADMIN_SUBS = os.environ["ADMIN_SUBS"].split(",")
SYSTEM_USERNAME = os.environ["SYSTEM_USERNAME"]
SYSTEM_PASSWORD = hashlib.sha256(os.environ["SYSTEM_PASSWORD"].encode()).digest()
INTERNAL_JWT_KEY = jwk.construct(
    key_data=os.environ["INTERNAL_JWT_KEY"],
    algorithm="HS256",
)


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

    async def __call__(self, request: Request) -> str | None:
        if not self._data:
            raise RuntimeError(
                "Provider not initialized! Make sure to call setup() in app lifespan"
            )
        authorization = await super().__call__(request)
        scheme, token_data = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            return None
        return token_data


account_provider = OIDCAccountProvider(OIDC_PROVIDER)
system_provider = OAuth2PasswordBearer(
    tokenUrl="auth/token",
    scheme_name="System authorization",
    scopes={"ingest": "Ingestion service"},
    auto_error=False,
)
assert isinstance(system_provider.model, OAuth2)
assert system_provider.model.flows.password
system_issuer = system_provider.model.flows.password.tokenUrl
system_scopes = system_provider.model.flows.password.scopes


async def valid_token(
    security_scopes: SecurityScopes,
    authorization: Annotated[str | None, Depends(account_provider)],
    authorization2: Annotated[str | None, Depends(system_provider)],
) -> TokenData:
    assert authorization == authorization2
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided",
            headers={"WWW-Authenticate": authenticate_value},
        )
    assert account_provider._data
    token_keys = {
        account_provider._data.issuer: account_provider._data.keys,
        system_issuer: {"": INTERNAL_JWT_KEY},
    }
    try:
        unverified_token = jwt.decode(
            authorization,
            key=None,  # type: ignore[arg-type]
            options={"verify_signature": False, "verify_aud": False},
        )
        issuer = unverified_token["iss"]
        key = token_keys[issuer]
        token = TokenData.model_validate(
            jwt.decode(authorization, key=key, issuer=issuer, audience="account")
        )
        # at this point token signature is confirmed
        if token.azp != OAUTH_CLIENT_ID:
            raise RuntimeError(
                f"Token authorized party {token.azp} does not match {OAUTH_CLIENT_ID=}"
            )
    except (JWTError, ValidationError, KeyError, RuntimeError) as ex:
        logger.warning(str(ex))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided",
            headers={"WWW-Authenticate": authenticate_value},
        )
    for scope in security_scopes.scopes:
        if scope not in token.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Insufficient permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return token


async def authorized_user(
    token: Annotated[TokenData, Depends(valid_token)]
) -> CurrentUser:
    return CurrentUser(
        sub=token.sub,
        username=token.preferred_username,
        email=token.email,
        name=token.name,
        scopes=token.scopes,
    )


AuthorizedUser = Annotated[CurrentUser, Depends(authorized_user)]


async def administrator(user: AuthorizedUser) -> CurrentUser:
    # TODO: better to have account provider set scopes correctly
    if user.sub not in ADMIN_SUBS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions",
        )
    return user


Administrator = Annotated[CurrentUser, Depends(administrator)]

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.get("/profile", response_model=CurrentUser)
async def read_profile(user: AuthorizedUser):
    return user


@router.get("/admin", response_model=CurrentUser)
async def read_profile_admin(user: Administrator):
    return user


@router.post("/token", response_model=Token)
async def system_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    valid_user = form_data.username == SYSTEM_USERNAME
    valid_pass = hashlib.sha256(form_data.password.encode()).digest() == SYSTEM_PASSWORD
    valid_client = form_data.client_id == OAUTH_CLIENT_ID
    if not (valid_user and valid_pass and valid_client):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided",
        )
    scopes = (scope for scope in form_data.scopes if scope in system_scopes)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    token = TokenData(
        exp=now + datetime.timedelta(hours=4),
        iat=now,
        iss=system_issuer,
        aud="account",
        sub=form_data.username,
        typ="Bearer",
        azp=form_data.client_id,  # type: ignore[arg-type]
        scope=" ".join(scopes),
        email="none",
        name="System User",
        preferred_username=form_data.username,
        given_name="System",
        family_name="User",
    )
    token_data = jwt.encode(token.model_dump(), key=INTERNAL_JWT_KEY)
    return Token(access_token=token_data, token_type="Bearer")
