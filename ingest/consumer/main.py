import logging
import asyncio
import tempfile
import os

from aio_pika import ExchangeType, connect_robust
from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError

from .message import AWSEvent, AWSRecord
from .shared import s3util

logger = logging.getLogger(__name__)


async def process(event: AWSRecord):
    # TODO: restapi call to register new file and record start of conversion
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = os.path.join(tmpdir, "input.root")
        logger.info(f"Temporary file: {tmpfile}")
        async with s3util.get_client("s3") as client:
            result = await client.get_object(
                Bucket="transfer-inbox", Key=event.s3.object.key
            )
            body = result["Body"]
            with open(tmpfile, "wb") as fout:
                logger.info("Starting download")
                async for chunk in body.iter_chunks(chunk_size=32 * 1024):  # type: ignore[attr-defined]
                    fout.write(chunk)
                logger.info("Finished download")
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "convert.py",
            tmpfile,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout
        logger.info("Starting conversion process")
        while line := await proc.stdout.readline():
            print(line.rstrip().decode())
        stdout, stderr = await proc.communicate()
        print(f"[root exited with {proc.returncode}]")
        if stdout:
            print(f"[stdout]\n{stdout.decode()}")
        if stderr:
            print(f"[stderr]\n{stderr.decode()}")

    # TODO: restapi call to declare conversion (partially?) finished


async def receive(message: AbstractIncomingMessage):
    assert message.routing_key == "bucket.transfer-notifier"
    try:
        data = AWSEvent.model_validate_json(message.body)
        if len(data.Records) != 1:
            raise ValueError(f"More than one record")
        event = data.Records[0]
    except (ValueError, ValidationError) as ex:
        logger.error(f"Failed to parse incoming message {message}: {ex}")
        return await message.reject(requeue=False)
    logger.debug(f" [x] {message.routing_key}:{data}")
    async with message.process(requeue=True):
        await process(event)


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

        await channel.set_qos(prefetch_count=0)
        logger.info(" [*] Waiting for messages.")
        async with queue.iterator() as iterator:
            async for message in iterator:
                await receive(message)


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    # TODO: catch graceful termination
    exit(asyncio.run(main()))
