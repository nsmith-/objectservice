import asyncio
import os

from aio_pika import connect_robust
from aiobotocore.session import get_session
from botocore.exceptions import ClientError


def _get_client(service: str):
    session = get_session()
    return session.create_client(
        service,
        region_name="default",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    )


async def setup_notification_queue(exchange_name: str, queue_name: str):
    connection = await connect_robust(
        url=os.environ["AMQP_URL"],
    )
    async with connection:
        channel = await connection.channel()
        await channel.queue_delete(queue_name)
        await channel.exchange_delete(exchange_name)
        exchange = await channel.declare_exchange(exchange_name, "topic", durable=True)
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange, "#")  # TODO: can just bind queue_name


async def main() -> int:
    servertype: str = "MinIO"  # | RadosGW

    # Set up buckets
    async with _get_client("s3") as client:
        config = {"LocationConstraint": "default:ec42"}
        try:
            response = await client.create_bucket(
                Bucket="transfer-inbox", CreateBucketConfiguration=config
            )
        except ClientError as ex:
            if ex.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                print(ex.response)

    # Set up OpenID Connect
    # For RadosGW we use IAM client to setup this
    # For Minio, it is set in environment variables
    if servertype != "MinIO":
        async with _get_client("iam") as client:
            try:
                response = await client.list_open_id_connect_providers()
                print(response)
            except ClientError as ex:
                print(ex.response)

    # TODO: Create role and set bucket policy

    # Set up notification topics
    # For RadosGW, we can use the SNS client
    # https://docs.ceph.com/en/latest/radosgw/notifications/#create-a-topic
    # For Minio it has to be set up via environment variables
    exchange_name = os.environ["AMQP_EXCHANGE"]
    queue_name = os.environ["AMQP_TRANSFER_TOPIC"]
    if servertype != "MinIO":
        async with _get_client("sns") as client:
            try:
                response = await client.create_topic(
                    Name=queue_name,
                    Attributes={
                        "push-endpoint": os.environ["AMQP_URL"],
                        "persistent": "true",
                        "amqp-exchange": exchange_name,
                    },
                )
            except ClientError as ex:
                print(ex.response)

    await setup_notification_queue(exchange_name, queue_name)

    # Bucket notification
    notification_events = [
        "s3:ObjectCreated:*",
        "s3:ObjectRemoved:*",
    ]
    if servertype != "MinIO":
        notification_config = {
            "TopicConfigurations": [
                {
                    "Id": "transfer-notifier-config",
                    "TopicArn": "arn:aws:sns:default::" + queue_name,
                    "Events": notification_events,
                },
            ]
        }
    else:
        notification_config = {
            "QueueConfigurations": [
                {
                    "Id": "transfer-notifier-config",
                    "QueueArn": "arn:minio:sqs::RABBITMQ:amqp",
                    "Events": notification_events,
                }
            ],
        }
    async with _get_client("s3") as client:
        response = await client.put_bucket_notification_configuration(
            Bucket="transfer-inbox",
            NotificationConfiguration=notification_config,
            SkipDestinationValidation=False,
        )

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
