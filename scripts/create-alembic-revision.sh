#!/usr/bin/env bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <message>"
    exit 1
fi

# check postgres is running and set up a temporary port forward
kubectl wait --for=condition=Available --timeout 5m deployment/postgres-deployment
kubectl port-forward deployment/postgres-deployment 5432:5432 &
export DB_URL=postgresql://postgres:geese@localhost:5432/app
pushd restapi
alembic revision --autogenerate -m "$1"
popd
kill %