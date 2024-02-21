import json
import logging
import asyncio
import os

from aio_pika import ExchangeType, connect_robust
from aio_pika.abc import AbstractIncomingMessage

logger = logging.getLogger(__name__)


async def process(message: AbstractIncomingMessage):
    async with message.process(requeue=True):
        assert message.routing_key == "bucket.transfer-notifier"
        # TODO: message schema
        data = json.loads(message.body)  # TODO: error here = reject without requeue
        # TODO: restapi call to register new file and record start of conversion
        logger.debug(f" [x] {message.routing_key!r}:{data!r}")
    # TODO: subprocess to run conversion
    # TODO: restapi call to declare conversion (partially?) finished


async def main():
    amqp_url = os.environ["AMQP_URL"]
    exchange_name = os.environ["AMQP_EXCHANGE"]
    queue_name = os.environ["AMQP_TRANSFER_TOPIC"]
    connection = await connect_robust(url=amqp_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            exchange_name, ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange, queue_name)

        await channel.set_qos(prefetch_count=1)
        logger.info(" [*] Waiting for messages.")
        async with queue.iterator() as iterator:
            async for message in iterator:
                await process(message)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # TODO: catch graceful termination
    exit(asyncio.run(main()))
