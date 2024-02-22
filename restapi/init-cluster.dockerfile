FROM restapi

COPY alembic /code/alembic

COPY alembic.ini init-cluster.sh /code/

CMD ["./init-cluster.sh"]
