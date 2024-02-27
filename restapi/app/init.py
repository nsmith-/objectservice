import asyncio
import logging
import os

from .shared import s3util

logger = logging.getLogger(__name__)


async def main() -> int:
    servertype: str = os.environ["S3_VENDOR"]
    if servertype not in ("MinIO", "RadosGW"):
        raise RuntimeError(f"Unsupported or missing S3_VENDOR: {servertype!r}")

    # Set up OpenID Connect
    # For RadosGW we use IAM client to setup this
    # For Minio, it is set in environment variables
    if servertype == "RadosGW":
        async with s3util.get_client("iam") as client:
            oidc_provider_arn = await s3util.register_oidc_provider(
                client, os.environ["OIDC_PROVIDER"], [os.environ["OAUTH_CLIENT_ID"]]
            )
            # TODO: create roles via REST endpoint
            await s3util.create_oidc_role(
                client, oidc_provider_arn, "ncsmith", "probablywrong"
            )

    # Set up notification topics
    # For Minio it has to be set up via environment variables and there is only one
    queue_name = os.environ["AMQP_TRANSFER_TOPIC"]
    topic_arn = "arn:minio:sqs::RABBITMQ:amqp"
    if servertype == "RadosGW":
        async with s3util.get_client("sns") as client:
            topic_arn = await s3util.register_notification_topic(client, queue_name)

    # Set up transfer-inbox bucket with notifications
    notification_events: "list[s3util.EventType]" = [
        "s3:ObjectCreated:*",
        "s3:ObjectRemoved:*",
    ]
    notification_config: "s3util.NotificationConfigurationTypeDef" = {
        "TopicConfigurations": [
            {
                "Id": "transfer-notifier-config",
                "TopicArn": topic_arn,
                "Events": notification_events,
            }
        ],
        "QueueConfigurations": [
            {
                "Id": "transfer-notifier-config",
                "QueueArn": topic_arn,
                "Events": notification_events,
            }
        ],
    }
    if servertype == "RadosGW":
        del notification_config["QueueConfigurations"]
    else:
        del notification_config["TopicConfigurations"]

    async with s3util.get_client("s3") as client:
        await s3util.create_bucket(client, "transfer-inbox")
        # allow FTS incoming data with cmsuser account
        await s3util.set_bucket_policy(
            client=client,
            bucket="transfer-inbox",
            principal="arn:aws:iam:::user/cmsuser",
            policy_type="read-write",
        )
        await client.put_bucket_notification_configuration(
            Bucket="transfer-inbox",
            NotificationConfiguration=notification_config,
            SkipDestinationValidation=False,
        )

    return 0


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    exit(asyncio.run(main()))
