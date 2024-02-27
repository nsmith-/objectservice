#!/usr/bin/env bash
set -e

# by default podman tries to use NFS build root and has trouble so we use /tmp
COMMON="--root /tmp/$(whoami)/"

podman $COMMON build -t shared -f shared/shared.dockerfile ./shared
podman $COMMON build -t restapi -f restapi/restapi.dockerfile ./restapi
podman $COMMON build -t init-cluster -f restapi/init-cluster.dockerfile ./restapi
podman $COMMON build -t ingest -f ingest/ingest.dockerfile ./ingest

podman $COMMON login imageregistry.fnal.gov:443
podman $COMMON push restapi imageregistry.fnal.gov:443/objectservice/restapi:dev
podman $COMMON push init-cluster imageregistry.fnal.gov:443/objectservice/init-cluster:dev
podman $COMMON push ingest imageregistry.fnal.gov:443/objectservice/ingest:dev
