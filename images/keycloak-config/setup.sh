#!/usr/bin/env sh
set -eu

# Wait for keycloak to be running
kubectl rollout status statefulsets.apps "$KEYCLOAK_STATEFUL_SET"

if kcadm.sh help > /dev/null; then 
  alias kcadm=kcadm.sh
fi

kcadm config credentials --server "$KEYCLOAK_ENDPOINT" --realm master --user admin

if ! kcadm get realms/"$KEYCLOAK_REALM" > /dev/null; then
  kcadm create realms -s realm="$KEYCLOAK_REALM" -s enabled=true > /dev/null
fi

# Remove required attributes from user profiles
kcadm get realms/"$KEYCLOAK_REALM"/users/profile | jq 'del(.attributes.[].required)' | kcadm update realms/"$KEYCLOAK_REALM"/users/profile -f -

CID=$(kcadm get clients -q clientId="$KEYCLOAK_CLIENT" -r "$KEYCLOAK_REALM" -F id --format csv --noquotes || true)
if [ -z "$CID" ]; then
  CID=$(kcadm create clients -i \
    -r "$KEYCLOAK_REALM" \
    -s clientId="$KEYCLOAK_CLIENT" \
    -s enabled=true \
    -s protocol=openid-connect \
    -s publicClient=true \
    -s 'attributes."pkce.code.challenge.method"'="S256" \
    -s "redirectUris=$KEYCLOAK_CLIENT_REDIRECTS" \
    -s "webOrigins=$KEYCLOAK_CLIENT_ORIGINS")
else
  kcadm update clients/"$CID" \
    -r "$KEYCLOAK_REALM" \
    -s "redirectUris=$KEYCLOAK_CLIENT_REDIRECTS" \
    -s "webOrigins=$KEYCLOAK_CLIENT_ORIGINS"
fi

# Create/Update the admin role
ADMIN_ROLE_NAME="${ADMIN_ROLE_NAME:-"admin"}"
ROLEID=$(kcadm get-roles -r "$KEYCLOAK_REALM" --cid "$CID" --rolename "$ADMIN_ROLE_NAME" -F id --format csv --noquotes || true)
if [ -z "$ROLEID" ]; then
  # The `-i` option returns the role name instead of the ID
  ROLEID=$(kcadm create clients/"$CID"/roles -o -F id \
    -r "$KEYCLOAK_REALM" \
    -s name="$ADMIN_ROLE_NAME" \
    -s description="Platform administrator role" | jq -r ".id")
fi

# Create/Update the historical API roles 
HISTORICAL_READ_ROLE_NAME="${HISTORICAL_READ_ROLE_NAME:-"historical-read"}"
ROLEID=$(kcadm get-roles -r "$KEYCLOAK_REALM" --cid "$CID" --rolename "$HISTORICAL_READ_ROLE_NAME" -F id --format csv --noquotes || true)
if [ -z "$ROLEID" ]; then
  # The `-i` option returns the role name instead of the ID
  ROLEID=$(kcadm create clients/"$CID"/roles -o -F id \
    -r "$KEYCLOAK_REALM" \
    -s name="$HISTORICAL_READ_ROLE_NAME" \
    -s description="Historical API read access" | jq -r ".id")
fi

HISTORICAL_WRITE_ROLE_NAME="${HISTORICAL_WRITE_ROLE_NAME:-"historical-write"}"
ROLEID=$(kcadm get-roles -r "$KEYCLOAK_REALM" --cid "$CID" --rolename "$HISTORICAL_WRITE_ROLE_NAME" -F id --format csv --noquotes || true)
if [ -z "$ROLEID" ]; then
  # The `-i` option returns the role name instead of the ID
  ROLEID=$(kcadm create clients/"$CID"/roles -o -F id \
    -r "$KEYCLOAK_REALM" \
    -s name="$HISTORICAL_WRITE_ROLE_NAME" \
    -s description="Historical API write access" | jq -r ".id")
fi

# Create/Update the system service role
SYSTEM_SERVICE_ROLE_NAME="${SYSTEM_SERVICE_ROLE_NAME:-"system-service"}"
ROLEID=$(kcadm get-roles -r "$KEYCLOAK_REALM" --cid "$CID" --rolename "$SYSTEM_SERVICE_ROLE_NAME" -F id --format csv --noquotes || true)
if [ -z "$ROLEID" ]; then
  # The `-i` option returns the role name instead of the ID
  ROLEID=$(kcadm create clients/"$CID"/roles -o -F id \
    -r "$KEYCLOAK_REALM" \
    -s name="$SYSTEM_SERVICE_ROLE_NAME" \
    -s description="Systems services role" | jq -r ".id")
fi

echo "$SYSTEM_ACCOUNTS" | tr , '\n' | while read NAME; do
  ACCOUNT_NAME="$ACCOUNTS_PREFIX-$NAME"

  ACCOUNT_ID=$(kcadm get users -r "$KEYCLOAK_REALM" -q "username=$ACCOUNT_NAME" -q "exact=true" | jq -r ".[0].id")
  if [ "$ACCOUNT_ID" = "null" ]; then
    ACCOUNT_ID=$(kcadm create users -i \
      -r "$KEYCLOAK_REALM" \
      -s username="$ACCOUNT_NAME" \
      -s enabled=true)
  fi

  kcadm add-roles -r "$KEYCLOAK_REALM" --uid "$ACCOUNT_ID" --cid "$CID" --roleid "$ROLEID"

  SECRET_NAME="$SECRETS_PREFIX-$NAME-credentials"
  if ! kubectl get secrets "$SECRET_NAME"; then
    ACCOUNT_PASSWORD="$(LC_ALL=C tr -dc A-Za-z0-9 </dev/urandom | head -c 16)"
    kubectl create secret generic "$SECRET_NAME" \
      --from-literal=username="$ACCOUNT_NAME" \
      --from-literal=password="$ACCOUNT_PASSWORD"
    kcadm set-password -r "$KEYCLOAK_REALM" --userid "$ACCOUNT_ID" --new-password "$ACCOUNT_PASSWORD"
  fi
done
