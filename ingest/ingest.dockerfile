FROM docker.io/rootproject/root:6.30.04-ubuntu22.04

RUN curl https://bootstrap.pypa.io/get-pip.py | python3

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN python3 -m pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY consumer /code/consumer

COPY --from=shared /shared /code/consumer/shared

COPY convert.py /code/

CMD ["python3", "-m", "consumer.main"]
