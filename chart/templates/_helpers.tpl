{{/*
Expand the name of the chart.
*/}}
{{- define "folio.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "folio.fullname" -}}
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
Create chart label.
*/}}
{{- define "folio.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "folio.labels" -}}
helm.sh/chart: {{ include "folio.chart" . }}
{{ include "folio.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "folio.selectorLabels" -}}
app.kubernetes.io/name: {{ include "folio.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "folio.imageRef" -}}
{{- if or (contains "@" .repository) (regexMatch ":[^/]+$" .repository) -}}
{{- .repository -}}
{{- else if .tag -}}
{{- printf "%s:%s" .repository .tag -}}
{{- else -}}
{{- .repository -}}
{{- end -}}
{{- end }}

{{/*
Runtime Secret consumed by the app, the migrate initContainer, postgres, and
minio. GitOps/Momokaya deployments set secrets.existingSecret so secret
material is not stored in Helm values or release history.
*/}}
{{- define "folio.runtimeSecretName" -}}
{{- required "secrets.existingSecret is required; manage runtime secrets outside Helm values" .Values.secrets.existingSecret }}
{{- end }}

{{/*
Momokaya labels are applied to resource metadata and pod templates only. They
are not selector labels because the values change between ephemeral renders.
*/}}
{{- define "folio.momokayaLabels" -}}
{{- with .Values.momokaya }}
{{- if .envKind }}
momokaya.ee/env-kind: {{ .envKind }}
{{- end }}
{{- if .envId }}
momokaya.ee/env-id: {{ .envId }}
{{- end }}
{{- if .repo }}
momokaya.ee/repo: {{ .repo }}
{{- end }}
{{- end }}
{{- end }}

{{- define "folio.momokayaAnnotations" -}}
{{- with .Values.momokaya }}
{{- if .branch }}
momokaya.ee/branch: {{ .branch | quote }}
{{- end }}
{{- if .sha }}
momokaya.ee/sha: {{ .sha | quote }}
{{- end }}
{{- if .owner }}
momokaya.ee/owner: {{ .owner | quote }}
{{- end }}
{{- if .ticket }}
momokaya.ee/ticket: {{ .ticket | quote }}
{{- end }}
{{- if .epic }}
momokaya.ee/epic: {{ .epic | quote }}
{{- end }}
{{- with .cleanupPolicy }}
{{- if .ttl }}
momokaya.ee/cleanup-policy: {{ .ttl | quote }}
{{- end }}
{{- if .deleteAfter }}
momokaya.ee/delete-after: {{ .deleteAfter | quote }}
{{- end }}
{{- if hasKey . "retainOnFailure" }}
momokaya.ee/retain-on-failure: {{ .retainOnFailure | quote }}
{{- end }}
{{- end }}
{{- if .queueName }}
momokaya.ee/queue-name: {{ .queueName | quote }}
{{- end }}
{{- range $name, $url := .urls }}
{{- if $url.host }}
momokaya.ee/url.{{ $name }}: {{ printf "https://%s%s" $url.host (default "/" $url.path) | quote }}
{{- end }}
{{- if $url.service }}
momokaya.ee/url.{{ $name }}.service: {{ $url.service | quote }}
{{- end }}
{{- if $url.port }}
momokaya.ee/url.{{ $name }}.port: {{ $url.port | quote }}
{{- end }}
{{- if $url.kind }}
momokaya.ee/url.{{ $name }}.kind: {{ $url.kind | quote }}
{{- end }}
{{- if $url.readiness }}
momokaya.ee/url.{{ $name }}.readiness: {{ $url.readiness | quote }}
{{- end }}
{{- if $url.status }}
momokaya.ee/url.{{ $name }}.status: {{ $url.status | quote }}
{{- end }}
{{- if $url.exposure }}
momokaya.ee/url.{{ $name }}.exposure: {{ $url.exposure | quote }}
{{- end }}
{{- if $url.auth }}
momokaya.ee/url.{{ $name }}.auth: {{ $url.auth | quote }}
{{- end }}
{{- if $url.internalService }}
momokaya.ee/url.{{ $name }}.internalService: {{ $url.internalService | quote }}
{{- end }}
{{- if $url.internalPort }}
momokaya.ee/url.{{ $name }}.internalPort: {{ $url.internalPort | quote }}
{{- end }}
{{- if $url.platform }}
momokaya.ee/url.{{ $name }}.platform: {{ $url.platform | quote }}
{{- end }}
{{- if $url.deepLink }}
momokaya.ee/url.{{ $name }}.deepLink: {{ $url.deepLink | quote }}
{{- end }}
{{- if $url.protocol }}
momokaya.ee/url.{{ $name }}.protocol: {{ $url.protocol | quote }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
