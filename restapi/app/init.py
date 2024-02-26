import asyncio
import logging
import os
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from types_aiobotocore_iam.client import IAMClient
    from types_aiobotocore_s3.client import S3Client
    from types_aiobotocore_s3.type_defs import NotificationConfigurationTypeDef
    from types_aiobotocore_s3.literals import EventType
    from types_aiobotocore_sns.client import SNSClient

from aiobotocore.session import get_session
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@overload
def _get_client(service: Literal["s3"]) -> "S3Client": ...
@overload
def _get_client(service: Literal["sns"]) -> "SNSClient": ...
@overload
def _get_client(service: Literal["iam"]) -> "IAMClient": ...
def _get_client(service):
    session = get_session()
    return session.create_client(
        service,
        region_name="default",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    )


async def _create_bucket(
    client: "S3Client", bucket_name: str, location_constraint: str | None = None
):
    try:
        if location_constraint is None:
            await client.create_bucket(Bucket=bucket_name)
        else:
            await client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": location_constraint},  # type: ignore[typeddict-item]
            )
        logger.info(f"Bucket {bucket_name} created")
    except ClientError as ex:
        code = ex.response["Error"]["Code"]
        message = ex.response["Error"]["Message"]
        if code == "BucketAlreadyOwnedByYou":
            logger.info(f"Bucket {bucket_name} already exists")
            return
        logger.warning(f"Failed to create bucket {bucket_name}: {code}: {message}")


async def _register_oidc_provider():
    async with _get_client("iam") as client:
        try:
            response = await client.list_open_id_connect_providers()
            # prefix = "arn:aws:iam:::oidc-provider/"
            for provider in response["OpenIDConnectProviderList"]:
                logger.info(f"Existing OpenID connect provider: {provider['Arn']}")
        except ClientError as ex:
            logger.warning(ex.response)


RGW_TOPIC_PREFIX = "arn:aws:sns:default::"


async def _register_notification_topic(queue_name: str, purge: bool = False):
    async with _get_client("sns") as client:
        try:
            topics = [
                topic["TopicArn"] for topic in (await client.list_topics())["Topics"]
            ]
            logger.info(f"Existing topics: {topics}")
            if purge:
                for topic in topics:
                    await client.delete_topic(TopicArn=topic)
            if RGW_TOPIC_PREFIX + queue_name not in topics or purge:
                response = await client.create_topic(
                    Name=queue_name,
                    Attributes={
                        "push-endpoint": os.environ["AMQP_URL"],
                        "persistent": "true",
                        "amqp-exchange": os.environ["AMQP_EXCHANGE"],
                    },
                )
                logger.info(f"Created topic: {response['TopicArn']}")
        except ClientError as ex:
            logger.warning(ex.response["Error"])


async def main() -> int:
    servertype: str = os.environ["S3_VENDOR"]
    if servertype not in ("MinIO", "RadosGW"):
        raise RuntimeError(f"Unsupported or missing S3_VENDOR: {servertype!r}")

    # Set up buckets
    async with _get_client("s3") as client:
        await _create_bucket(client, "transfer-inbox")

    # Set up OpenID Connect
    # For RadosGW we use IAM client to setup this
    # For Minio, it is set in environment variables
    if servertype == "RadosGW":
        await _register_oidc_provider()

    # TODO: Create role and set bucket policy

    # Set up notification topics
    # For RadosGW, we can use the SNS client
    # For Minio it has to be set up via environment variables
    queue_name = os.environ["AMQP_TRANSFER_TOPIC"]
    if servertype == "RadosGW":
        await _register_notification_topic(queue_name)

    # Bucket notification
    notification_events: "list[EventType]" = [
        "s3:ObjectCreated:*",
        "s3:ObjectRemoved:*",
    ]
    notification_config: "NotificationConfigurationTypeDef" = {
        "TopicConfigurations": [
            {
                "Id": "transfer-notifier-config",
                "TopicArn": RGW_TOPIC_PREFIX + queue_name,
                "Events": notification_events,
            }
        ],
        "QueueConfigurations": [
            {
                "Id": "transfer-notifier-config",
                "QueueArn": "arn:minio:sqs::RABBITMQ:amqp",
                "Events": notification_events,
            }
        ],
    }
    if servertype == "RadosGW":
        del notification_config["QueueConfigurations"]
    else:
        del notification_config["TopicConfigurations"]
    async with _get_client("s3") as client:
        try:
            result = await client.get_bucket_notification_configuration(
                Bucket="transfer-inbox"
            )
            logger.debug(result)
            await client.put_bucket_notification_configuration(
                Bucket="transfer-inbox",
                NotificationConfiguration=notification_config,
                SkipDestinationValidation=False,
            )
        except ClientError as ex:
            logger.warning(ex.response["Error"])

    return 0


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    exit(asyncio.run(main()))
