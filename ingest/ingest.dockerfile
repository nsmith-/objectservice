FROM rootproject/root:6.30.04-ubuntu22.04

RUN curl https://bootstrap.pypa.io/get-pip.py | python3

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN python3 -m pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY consumer /code/consumer

CMD ["python3", "-m", "consumer.main"]