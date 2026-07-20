# Operation {#sec:operation}

The following sections document standard procedures for regular operation of
the platform.

## User Management

The platform utilizes a centralized user management approach built on top
of Keycloak[^keycloak] and OpenID Connect[^oidc] (OIDC from herein after) to
allow users to have a Single Sign On (SSO) experience between all the different
platform services. Services to share authentication and authorization logic, and
administrators to easily manage users and their roles.

When installing or upgrading the platform, a maintenance job is automatically
started that will create the necessary Keycloak configurations, including a
realm, a client, and roles for administration and system services to properly
operate. As such, administrators don't need to configure any service accounts
and/or roles for the platform to start functioning normally and only need to
configure user accounts for external participants as needed.

[^keycloak]: <https://www.keycloak.org/>

[^oidc]: <https://openid.net/developers/how-connect-works/>

### Accessing Keycloak management

Keycloak is exposed under the path `https://<host>/auth`, where `<host>` is
the domain name configured in @sec:installation, navigating to `/auth` directly
will redirect to a login form gating access to the administration console. An
administration account is automatically created during installation with the
username `admin` and a securely generated password, which can be recovered with
access to the Kubernetes cluster and by running the following command:

```
$ kubectl get secrets dt4mob-keycloak-admin -o jsonpath="{.data.password}" | base64 -d
```

This will print the password to the terminal's standard output. Using the
obtained credentials and submitting the login form allows access to Keycloak's
administration console.

![Keycloak administration console](./user-manual/assets/03-operation/keycloak-admin-master-realm.png)

Keycloak will display a banner warning that the account is a temporary admin
user and to create a permanent admin account. This Keycloak is provisioned
exclusively for the platform, and the credentials for the admin user are
securely generated; as such, it isn’t strictly needed to create a permanent
admin account.

Nonetheless, it might be useful to do so in order to provide a finer-grained
administration account or increase the admin account security by, for example,
adding 2FA. To do so, please consult the relevant Keycloak documentation
for instructions.

The next sections will all operate on the `dt4mob` realm; to switch, click on
the "Manage realms" link on the left sidebar and then on the `dt4mob` realm
name, which should be highlighted as a link.

![Switching realms in Keycloak](./user-manual/assets/03-operation/keycloak-admin-manage-realms.png)

### Adding a user

A fresh installation will only contain users for the platform's services. To
create a user account for an external entity to interact with the platform,
start by navigating to the "Users" link on the left sidebar (ensure the current
realm is the `dt4mob` realm).

![List of users in the realm](./user-manual/assets/03-operation/keycloak-dt4mob-users.png)

Then press the "Add user" button in the interface; this will bring up a form
for creating a new user. The only mandatory field is the username, which
must be unique and will be used in authentication. However, if the user is to
have access to the visualization Grafana instance, then an email must also be
specified otherwise the user won't be able to access it even with the correct
roles. The other fields can be left empty or filled as required; for more
details, consult the relevant Keycloak documentation.

Submitting the form will create the user and redirect to its details page.

![User details page](./user-manual/assets/03-operation/keycloak-user-details.png)

At this point it still won't be possible to use the account as it doesn't have
any credentials to use for authentication. To assign a password, navigate to
the "Credentials" tab in the user's details page and press the "Set password"
button. This will trigger a popup with a form to set a password for the user.

![Setting the user's password](./user-manual/assets/03-operation/keycloak-set-password.png)

The password can be set as temporary (the default), in which case the user
will be prompted to change it after the first login; configure this toggle as
relevant for the created user. Fill the form with a proper password, confirm
it, and submit the form. The user will now have credentials in the form of its
username and the password that was just configured. These should be communicated
to the external entity through a secure channel.

### Assigning roles {#sec:assign-role}

A newly created account will not have any platform roles assigned to it. This
allows it to access Ditto and the visualization service and interact with things
that are allowed by their respective policies.

However, to access other services such as the historical data API, the
certificate issuance service, or even to have administrative access, roles
must be assigned to the user.

To assign a role to a user, navigate to its user details page, then to the "Role
mapping" tab, and press the "Assign Role" button. This will open a dropdown with
two options; select the "Client roles" option.

![Assigning platform roles](./user-manual/assets/03-operation/keycloak-assign-client-roles.png)

This will open a popup with a list of roles that can be assigned to the user; of
these, only the ones with the `ditto` Client ID are relevant for authorization
within the context of the platform's services.

![Client roles selection](./user-manual/assets/03-operation/keycloak-select-client-roles.png)

Roles can be created by administrators for use in Ditto policies, and the
platform itself defines a set of special roles that grant access to extra
services within the platform. The table below lists these special roles and the
extra access they concede.

<!-- &nbsp; is used to pad the table column so that the column is not so small that it causes the text to be broken up -->

| Role&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Access granted                                                                                                                                                                              |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `admin`                                              | Grants full access to the platform including all things, all services, and ability to generate certificates impersonating other users.                                                      |
| `historical-read`                                    | Grants read access to the historical data API. It should be noted that there is no notion of policies in the historical data and as such all things are queryable by anyone with this role. |
| `historical-write`                                   | Grants write access to the historical data API, allowing backfilling of information from other systems.                                                                                     |
| `certificate-issuer`                                 | Grants access to the certificate issuance service, allowing the user to obtain valid client certificates that can be used to connect devices to Hono.                                       |

Table: Special platform roles

Simply select the roles that the user should have and finish by clicking
"Assign" at the bottom of the popup. Despite roles being assigned instantly
older sessions will still be using older tokens that do not have the roles. This
can be fixed either by waiting for the token to be refreshed, at which point it
will have the roles, or by logging out and logging back in. This will cause a
new token to be generated that will contain the new role assignment.

### Creating roles

As previously mentioned, administrators may create additional roles that can
then be used in policies to control access to things within the platform. This
can be useful since it allows defining authorization policies in terms of user
function instead of identity. For example, technicians may need access to all
gantries of the company in the country. Instead of defining each technician
in the policy for the gantries, a role can be created and assigned to the
technicians as required and the policy only needs to grant access to the role
once.

To define a new role, start by navigating to the "Clients" link on the left
sidebar (ensure the current realm is the `dt4mob` realm). A list of clients
should appear, including ones used internally by Keycloak and the `ditto`
client, which is the client used by the platform.

![Keycloak realm clients](./user-manual/assets/03-operation/keycloak-clients.png)

Pressing the link for the `ditto` client will open its client details page; from
here, navigate to the "Roles" tab, which will display a list of all the roles of
the client.

![Client roles list](./user-manual/assets/03-operation/keycloak-client-roles.png)

From here, press the "Create role", button which will trigger navigation to the
role creation form, insert the name of the new role and optionally a description
for it, and submit the form to finish creating the role. Assign the role to a
user as explained in @sec:assign-role to begin using it.

## Ditto

As previously mentioned, Eclipse Ditto is the backend that allows for the storage
and querying of digital twins in the DT4Mob platform. The following sections
explain how to access Ditto, create policies, and gain DevOps privileges.

### Accessing Ditto

Ditto is exposed under the paths `https://<host>/ui` and `https://<host>/api`,
where `<host>` is the domain name configured in @sec:installation, for the
Web UI and the API, respectively. Navigating to the Web UI will automatically
redirect to Keycloak's login form if the user has no current authentication
session. No role is required to interact with Ditto. API access requires that
the access token be obtained previously and passed as a bearer token in the
`Authorization` header.

### Defining policies

Policies control access to themselves and things within Ditto. A policy is
composed of a set of entries, each defining for a set of subjects the allowed
resource operations. A thing has exactly one policy associated with it that
controls its access. Policies can import from one another to allow reusing logic
for common authorization decisions. For more information, consult the relevant
documentation[^policies].

A policy can be created either through the Web UI in the "policies" tab or
through the API. To create a policy through the Web UI, ensure that no policy
is currently selected and navigate to the "JSON" tab in the right pane (not the
navigation bar).

![Ditto Web UI policies view](./user-manual/assets/03-operation/ditto-create-policy.png)

From here, press the "create" button on the right pane to begin editing the new
policy; it won't be possible to edit any of the fields before doing so. Define
a unique policy ID that must follow the format `<namespace>:<name>`, and write
the policy definition in the large text box below it. For details on the policy
definition syntax, consult the Ditto documentation.

On the left pane, under the "Who am I" section is a list of all the subjects
the current user represents. These are directly derived from the access token
obtained from Keycloak. The table below lists the different subjects extracted
from the token that can be in policy definitions:

| Subject &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Description                                                                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `keycloak:sub:<uid>`                                                                         | The `sub` field of the access token, uniquely identifies the user. Shouldn't be used in policy definitions since it isn't obvious what the actual user is from the UID.                                                                                                                   |
| `keycloak:user:<uid>`                                                                        | The username of the user extracted from the access token, uniquely identifies the user at this point in time but might be reused for another user later if this user is deleted and a new one then created. Preferred over `keycloak:sub` but in most cases roles should be used instead. |
| `keycloak:role:<uid>`                                                                        | Client roles extracted from the access token. Usually the best option when defining policies as it allows defining access by function instead of identity of the user, and is also easier to manage.                                                                                      |

Table: Subjects obtained from the access token

[^policies]: <https://eclipse.dev/ditto/basic-policy.html>

#### Allowing Hono messages

Policies need to include a special subject to allow for messages to be accepted
from the Hono connection to things controlled by the policy. This is done by
adding the following entry to the policy:

```{.json caption="Hono connection policy entry"}
"HONO": {
  "subjects": {
    "pre-authenticated:hono-connection-<tenant>": {
      "type": "Connection to Eclipse Hono"
    }
  },
  "resources": {
    "thing:/": {
      "grant": [
        "READ",
        "WRITE"
      ],
      "revoke": []
    },
    "message:/": {
      "grant": [
        "READ",
        "WRITE"
      ],
      "revoke": []
    },
    "policy:/": {
      "grant": [
        "READ"
      ],
      "revoke": []
    }
  },
  "importable": "implicit"
}
```

Where `<tenant>` is the name of the tenant that was configured in
@sec:installation.

#### Allowing historical exporting

The historical exporter connection also requires a special entry to allow for
the evolution of things to be stored. This allows for things to be excluded
from the historical database such that only the strictly necessary things are
saved, helping with costs, performance, and compliance.

```{.json caption="Hono connection policy entry"}
"KAFKA_EXPORT": {
  "subjects": {
    "pre-authenticated:kafka-export-connection-<tenant>": {
      "type": "Kafka Connection"
    }
  },
  "resources": {
    "thing:/": {
      "grant": [
        "READ"
      ],
      "revoke": []
    },
    "policy:/": {
      "grant": [
        "READ"
      ],
      "revoke": []
    }
  },
  "importable": "implicit"
}
```

Where `<tenant>` is the name of the tenant that was configured in
@sec:installation.

### DevOps access

Some operations, such as managing inbound (Hono) and outbound (historical
exporter) connections or running administration operations in Ditto, require
the use of a special account called the DevOps. This account does not utilize
the centralized user management, and its credentials are generated during
installation in-cluster.

The username is `devops`, and the password can be recovered using the following
command:

```sh
$ kubectl get secret dt4mob-ditto-gateway-secret -o jsonpath="{.data.devops-password}" | base64 -d
```

These credentials can then be used through basic authentication in the APIs that
require the use of this account or in the Web UI by pressing the "Authorize"
button on the far right of the navigation bar. This will trigger a popup with
two forms for authentication. The top one is for regular authentication using
Keycloak, while the bottom one is for DevOps authentication.

Upon inserting the credentials and submitting the form, access to the
"Connections" and "Operations" pages will be possible without receiving any
missing authentication errors.

Note: Sometimes the "Basic" radio button beside the DevOps login form is not
selected (this is due to a bug in Ditto), and authentication won't progress in
that case. To fix it, simply select the radio button and submit the form again.
