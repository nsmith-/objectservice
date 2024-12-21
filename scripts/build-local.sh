#!/usr/bin/env bash
set -e

eval $(minikube docker-env)
docker build -t shared -f shared/shared.dockerfile ./shared
docker build -t keycloak -f keycloak/keycloak.dockerfile ./keycloak
docker build -t restapi -f restapi/restapi.dockerfile ./restapi
docker build -t init-cluster -f restapi/init-cluster.dockerfile ./restapi
docker build -t ingest -f ingest/ingest.dockerfile ./ingest
docker build -t frontend -f frontend/frontend.dockerfile ./frontend