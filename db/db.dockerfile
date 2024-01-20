FROM postgres:12

COPY test-local-initdb.sql /docker-entrypoint-initdb.d/