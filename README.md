Testing on MiniKube:
```bash
minikube start
minikube addons enable ingress
kubectl apply -f deployments/test
```