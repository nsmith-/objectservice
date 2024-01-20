import os

from authlib.integrations.starlette_client import (OAuth, OAuthError,
                                                   StarletteOAuth2App)
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse


def patch_for_testenv(auth: StarletteOAuth2App):
    prefix_innetwork = "http://keycloak"
    prefix_external = "http://localhost"
    client_uris = ["issuer", "authorization_endpoint", "end_session_endpoint"]
    for uri in client_uris:
        if auth.server_metadata[uri].startswith(prefix_innetwork):
            auth.server_metadata[uri] = (
                prefix_external + auth.server_metadata[uri][len(prefix_innetwork) :]
            )


oauth = OAuth()
oauth.register(
    "default",
    server_metadata_url=os.environ["OAUTH_WELLKNOWN_URL"],
    client_id=os.environ["OAUTH_CLIENT_ID"],
    client_secret=os.environ["OAUTH_CLIENT_SECRET"],
    client_kwargs={"scope": "openid profile email"},
)
default_auth: StarletteOAuth2App = oauth.default

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.get("/login")
async def login_oauth(request: Request):
    redirect_uri = request.url_for("auth_oauth")
    return await default_auth.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_oauth(request: Request):
    try:
        token = await default_auth.authorize_access_token(request)
    except OAuthError as ex:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authorization failed")
    print(token)
    user = token.get("userinfo")
    id_token = token.get("id_token")

    if user:
        request.session["user"] = dict(user)
    return RedirectResponse(url="/")


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")
