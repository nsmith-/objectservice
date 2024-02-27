import json
import logging
import os
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from types_aiobotocore_iam.client import IAMClient
    from types_aiobotocore_s3.client import S3Client
    from types_aiobotocore_s3.type_defs import NotificationConfigurationTypeDef
    from types_aiobotocore_s3.literals import EventType
    from types_aiobotocore_sns.client import SNSClient
    from types_aiobotocore_sts.client import STSClient

from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from . import jwtutil

logger = logging.getLogger(__name__)


RGW_TOPIC_PREFIX = "arn:aws:sns:default::"
RGW_OIDCPROVIDER_PREFIX = "arn:aws:iam:::oidc-provider/"


@overload
def get_client(service: Literal["s3"]) -> "S3Client": ...
@overload
def get_client(service: Literal["sns"]) -> "SNSClient": ...
@overload
def get_client(service: Literal["sts"]) -> "STSClient": ...
@overload
def get_client(service: Literal["iam"]) -> "IAMClient": ...
def get_client(service):
    session = get_session()
    return session.create_client(
        service,
        region_name="default",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    )


async def create_bucket(
    client: "S3Client", bucket_name: str, location_constraint: str | None = None
) -> str:
    """Creates a bucket

    Location constraints can name a RadosGW pool if previously configured

    Returns bucket name on success
    """
    try:
        if location_constraint is None:
            await client.create_bucket(Bucket=bucket_name)
        else:
            await client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": location_constraint},  # type: ignore[typeddict-item]
            )
        logger.info(f"Bucket {bucket_name} created")
        return bucket_name
    except ClientError as ex:
        code = ex.response["Error"]["Code"]
        if code == "BucketAlreadyOwnedByYou":
            return bucket_name
        raise


async def set_bucket_policy(
    client: "S3Client", bucket: str, principal: str, policy_type: Literal["read-write"]
):
    """Set one of a few canned policies on a bucket

    principal can either be:
     - a user ARN, e.g. arn:aws:iam:::user/cmsuser", or
     - a role ARN, e.g. "arn:aws:iam:::role/oidcuser"
    policy_type: read-write, read, etc.
    """
    # TODO: other policies
    if policy_type not in ("read-write"):
        raise ValueError(f"Unknown policy {policy_type}")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": [principal]},
                "Action": [
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListMultipartUploadParts",
                    "s3:AbortMultipartUpload",
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*",
                ],
            },
        ],
    }
    policy_document = json.dumps(policy, separators=(",", ":"))
    await client.put_bucket_policy(Bucket=bucket, Policy=policy_document)


async def register_oidc_provider(
    client: "IAMClient",
    oidc_provider_url: str,
    client_ids: list[str],
    purge: bool = False,
) -> str:
    """Register an OpenID connect provider

    For RadosGW we can use these to create temporary credentials

    oidc_provider_url should be an endpoint (e.g. with Keycloak, something like https://myauth.com/realms/myrealm)
    client_ids should be the clients you have registered with the endpoint
    thumbprints can be found via the keys the provider serves at it's JWKS URL

    Returns the provider ARN
    """
    if oidc_provider_url.startswith("https://"):
        oidc_provider_arn = RGW_OIDCPROVIDER_PREFIX + oidc_provider_url.removeprefix(
            "https://"
        )
    else:
        raise ValueError(f"Malformed OpenID connect provider URL: {oidc_provider_url}")
    providers = [
        provider["Arn"]
        for provider in (await client.list_open_id_connect_providers())[
            "OpenIDConnectProviderList"
        ]
    ]
    logger.info(f"Existing OpenID connect providers: {providers}")
    if purge:
        for provider in providers:
            await client.delete_open_id_connect_provider(
                OpenIDConnectProviderArn=provider
            )
    if oidc_provider_arn not in providers or purge:
        provider_data = await jwtutil.fetch_OIDCProviderData(oidc_provider_url)
        # RadosGW only allows up to 5
        thumbprints = provider_data.thumbprints[:5]
        logger.info(
            f"Recovered thumbprints {thumbprints} for provider {oidc_provider_url}"
        )
        result = await client.create_open_id_connect_provider(
            Url=oidc_provider_url,
            ClientIDList=client_ids,
            ThumbprintList=thumbprints,
        )
        if result["OpenIDConnectProviderArn"] != oidc_provider_arn:
            raise RuntimeError(
                f"Tried to register OpenID connect provider {oidc_provider_arn} but ARN is {result['OpenIDConnectProviderArn']}"
            )
        logger.info(f"Registered OpenID connect provider {oidc_provider_arn}")
    return oidc_provider_arn


async def create_oidc_role(
    client: "IAMClient", oidc_provider_arn: str, username: str, oidc_subject: str
):
    """Create a new role for use with S3

    oidc_provider_arn is as returned by a call to register_oidc_provider()
    username will be the internal S3 user/role name
    oidc_subject must match the 'sub' field of a JWT used to assume the role using the STS client
    """
    provider_attr_prefix = oidc_provider_arn.removeprefix(RGW_OIDCPROVIDER_PREFIX)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": [oidc_provider_arn]},
                "Action": ["sts:AssumeRoleWithWebIdentity"],
                "Condition": {
                    "StringEquals": {
                        provider_attr_prefix + ":sub": [oidc_subject],
                    }
                },
            }
        ],
    }
    policy_document = json.dumps(policy, separators=(",", ":"))
    try:
        response = await client.create_role(
            AssumeRolePolicyDocument=policy_document,
            RoleName=username,
        )
        if response["Role"]["RoleName"] != username:
            raise RuntimeError(
                f"Tried to create a role {username} but got {response['Role']['RoleName']}!"
            )
    except ClientError as ex:
        if "Error" in ex.response:
            code = ex.response["Error"]["Code"]
        else:
            # RadosGW does not conform to schema
            code = ex.response["Code"]  # type: ignore[typeddict-item]
        if code != "EntityAlreadyExists":
            raise
    # update instead
    await client.update_assume_role_policy(
        RoleName=username,
        PolicyDocument=policy_document,
    )
    # TODO: customize policy (for now just grant all on personal bucket)
    role_policy = {
        "Version": "2012-10-17",
        "Statement": {
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": f"arn:aws:s3:::{username}/*",
        },
    }
    policy_document = json.dumps(role_policy, separators=(",", ":"))
    await client.put_role_policy(
        RoleName=username,
        PolicyName=f"RolePolicy_{username}",
        PolicyDocument=policy_document,
    )
    return username


async def register_notification_topic(
    client: "SNSClient", queue_name: str, purge: bool = False
) -> str:
    topic_arn = RGW_TOPIC_PREFIX + queue_name
    try:
        topics = [topic["TopicArn"] for topic in (await client.list_topics())["Topics"]]
        logger.info(f"Existing topics: {topics}")
        if purge:
            for topic in topics:
                await client.delete_topic(TopicArn=topic)
        if topic_arn not in topics or purge:
            response = await client.create_topic(
                Name=queue_name,
                Attributes={
                    "push-endpoint": os.environ["AMQP_URL"],
                    "persistent": "true",
                    "amqp-exchange": os.environ["AMQP_EXCHANGE"],
                },
            )
            if response["TopicArn"] != topic_arn:
                raise RuntimeError(
                    f"Tried to create topic {topic_arn} but ended up with {response['TopicArn']}!"
                )
            else:
                logger.info(f"Created topic: {topic_arn}")
    except ClientError as ex:
        logger.error(ex.response["Error"])
    return topic_arn
