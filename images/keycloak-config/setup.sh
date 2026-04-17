#!/usr/bin/env sh
set -eux

kubectl rollout status statefulsets.apps "$KEYCLOAK_STATEFUL_SET"

if kcadm.sh help > /dev/null; then 
  alias kcadm=kcadm.sh
fi

kcadm config credentials --server "$KEYCLOAK_ENDPOINT" --realm master --user admin

if ! kcadm get realms/"$KEYCLOAK_REALM" > /dev/null; then
  kcadm create realms -s realm="$KEYCLOAK_REALM" -s enabled=true > /dev/null
fi

CID=$(kcadm get clients -q clientId="$KEYCLOAK_CLIENT" -r "$KEYCLOAK_REALM" -F id --format csv --noquotes)
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
