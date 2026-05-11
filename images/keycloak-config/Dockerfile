FROM alpine:3.22

RUN mkdir -p /opt
WORKDIR /opt

RUN apk add keycloak kubectl jq

COPY setup.sh /opt/setup.sh

ENTRYPOINT ["/opt/setup.sh"]
