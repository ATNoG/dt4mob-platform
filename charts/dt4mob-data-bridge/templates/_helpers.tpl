{{/*
Expand the name of the chart.
*/}}
{{- define "data-bridge.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "data-bridge.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create the standard labels.
*/}}
{{- define "data-bridge.labels" -}}
helm.sh/chart: {{ include "data-bridge.name" . }}
app.kubernetes.io/name: {{ include "data-bridge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | toString }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.labels }}
{{- toYaml . }}
{{- end }}
{{- end }}

{{/*
Create the annotations.
*/}}
{{- define "data-bridge.annotations" -}}
{{- with .Values.annotations }}
{{- toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels for the Deployment and Service.
*/}}
{{- define "data-bridge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "data-bridge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "data-bridge.serviceAccountName" -}}
{{- include "data-bridge.fullname" . }}
{{- end }}