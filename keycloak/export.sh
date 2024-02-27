# replace with correct pod name
export POD=keycloak-deployment-5c5974694c-pqmhb
kubectl exec $POD -- /opt/jboss/keycloak/bin/standalone.sh \
  -Djboss.socket.binding.port-offset=100 -Dkeycloak.migration.action=export -Dkeycloak.migration.provider=singleFile \
  -Dkeycloak.migration.realmName=test -Dkeycloak.migration.usersExportStrategy=REALM_FILE -Dkeycloak.migration.file=/tmp/test-realm.json
# Ctrl+C to leave
kubectl exec $POD -- cat /tmp/test-realm.json > keycloak/test-realm.json
