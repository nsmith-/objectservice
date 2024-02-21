#!/usr/bin/env bash
set -e

eval $(minikube docker-env)
docker build -t objectservice-keycloak -f keycloak/keycloak.dockerfile ./keycloak
docker build -t objectservice-restapi -f restapi/restapi.dockerfile ./restapi
docker build -t objectservice-init-cluster -f restapi/init-cluster.dockerfile ./restapi
docker build -t objectservice-ingest -f ingest/ingest.dockerfile ./ingest