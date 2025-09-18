{{/*
Expand the name of the chart.
*/}}
{{- define "dt4mob.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "dt4mob.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "dt4mob.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "dt4mob.labels" -}}
helm.sh/chart: {{ include "dt4mob.chart" . }}
{{ include "dt4mob.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "dt4mob.selectorLabels" -}}
app.kubernetes.io/name: {{ include "dt4mob.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Configuration for a server certificate
- (mandatory) "dot": the root scope (".") and
- (mandatory) "component": the name of the component
*/}}
{{- define "dt4mob.serverCertificate" -}}
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: {{ include "dt4mob.fullname" .dot }}-{{ .component }}-cert
  labels:
    {{- include "dt4mob.labels" .dot | nindent 4 }}
spec:
  commonName: {{ .component }}
  subject:
    organizationalUnits: ["DT4MOB;Hono"]
  secretName: {{ include "dt4mob.fullname" .dot }}-{{ .component }}-cert
  privateKey:
    algorithm: ECDSA
    size: 256
  issuerRef:
    name: {{ include "dt4mob.fullname" .dot }}-server-intermediate-ca-issuer
    kind: Issuer
    group: cert-manager.io
  keystores:
    jks:
      create: true
      passwordSecretRef:
        name: {{ include "dt4mob.keyStorePasswordSecret" .dot | quote }}
        key: "password"
{{- end }}

{{/*
Create the name of the service account to use for the controller
*/}}
{{- define "dt4mob.controller.serviceAccountName" -}}
{{- if .Values.controller.serviceAccount.create }}
{{- default (printf "%s-controller" (include "dt4mob.fullname" .)) .Values.controller.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.controller.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret with the keystore's password
*/}}
{{- define "dt4mob.keyStorePasswordSecret" -}}
{{ include "dt4mob.fullname" . }}-keystore-password-secret
{{- end }}
