#! /usr/bin/env bash

# Exit in case of error
set -e

docker-compose down -v --remove-orphans # Remove possibly previous broken stacks left hanging after an error
docker-compose build
docker-compose up -d
docker-compose exec -T restapi pip install pytest
docker-compose exec -T restapi pytest /code/app "$@"