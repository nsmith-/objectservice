#!/usr/bin/env bash

# Exit in case of error
set -e

minikube start
minikube addons enable ingress
./scripts/build-local.sh
kubectl apply -f manifest/test
kubectl wait --for=condition=Available --timeout 5m deployment/restapi-deployment
kubectl exec deployment/restapi-deployment -c restapi -- pytest /code/app
echo "Cluster can be accessed at `minikube ip`. Set 'objectservice' and 'keycloak' to this address in /etc/hosts"
echo "Run 'minikube delete' to clean up"