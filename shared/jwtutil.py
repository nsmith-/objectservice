import base64
import dataclasses
import hashlib
import logging

import httpx
from jose import jwk
from jose.backends.base import Key
from jose.exceptions import JWKError

logger = logging.getLogger(__name__)
OIDC_WELLKNOWN = "/.well-known/openid-configuration"


@dataclasses.dataclass
class OIDCProviderData:
    url: str
    issuer: str
    keys: dict[str, Key]
    thumbprints: list[str]

    def wellknown_url(self) -> str:
        return self.url + OIDC_WELLKNOWN


def thumbprint(key: Key) -> str:
    """Attempting to compute key thumbprint

    Per https://docs.ceph.com/en/latest/radosgw/STS/#how-to-obtain-thumbprint-of-an-openid-connect-provider-idp
    Currently not giving same value as what is found in the 'x5t' attribute
    """
    pem = key.to_pem()
    pem = pem.removeprefix(b"-----BEGIN CERTIFICATE-----\n")
    pem = pem.removesuffix(b"-----END CERTIFICATE-----\n")
    logger.info(pem)
    public_bytes = base64.b64decode(pem)
    sha1digest = hashlib.sha1(public_bytes).hexdigest()
    return sha1digest


async def fetch_OIDCProviderData(oidc_provider_url: str) -> OIDCProviderData:
    oidc_provider_url = oidc_provider_url.removesuffix(OIDC_WELLKNOWN)
    wellknown_url = oidc_provider_url + OIDC_WELLKNOWN
    async with httpx.AsyncClient() as client:
        config = (await client.get(wellknown_url)).json()
        key_data = (await client.get(config["jwks_uri"])).json()
    issuer = config["issuer"]
    keys = {}
    thumbprints = []
    for key in key_data["keys"]:
        try:
            keys[key["kid"]] = jwk.construct(key)
            if "x5t" in key:
                # TODO: compare with self-computed
                thumbprints.append(base64.b64decode(key["x5t"] + "==").hex())
        except JWKError as ex:
            logger.warning(f"Could not parse JWKS key {key['kid']}: {ex}")
    return OIDCProviderData(oidc_provider_url, issuer, keys, thumbprints)
