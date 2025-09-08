{{/*
Configuration for a server certificate
- (mandatory) "dot": the root scope (".") and
- (mandatory) "component": the name of the component
*/}}
{{- define "dt4mob.serverCertificate" -}}
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: {{ .dot.Release.Name }}-{{ .component }}-cert
spec:
  commonName: {{ .component }}
  subject:
    organizationalUnits: ["DT4MOB;Hono"]
  secretName: {{ .dot.Release.Name }}-{{ .component }}-cert
  privateKey:
    algorithm: ECDSA
    size: 256
  issuerRef:
    name: {{ .dot.Release.Name }}-server-intermediate-ca-issuer
    kind: Issuer
    group: cert-manager.io
{{- end }}
