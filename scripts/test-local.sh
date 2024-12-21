#!/usr/bin/env bash

# Exit in case of error
set -e

# podman machine set --cpus 4 --memory 8192 --rootful
minikube start --cpus=4 --memory="7GB"
minikube addons enable ingress
./scripts/build-local.sh
kubectl apply -f manifest/test
kubectl wait --for=condition=Available --timeout 5m deployment/restapi-deployment
kubectl exec deployment/restapi-deployment -c restapi -- pytest /code/app
echo "Add 127.0.0.1 for keycloak and objectservice to /etc/hosts and run minikube tunnel"
echo "Cluster can be accessed at https://objectservice/ while minikube tunnel is running"
echo "Run 'minikube delete' to clean up"