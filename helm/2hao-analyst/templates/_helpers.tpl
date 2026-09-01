{{/*
Expand the name of the chart.
*/}}
{{- define "2hao-analyst.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "2hao-analyst.fullname" -}}
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
Create chart labels
*/}}
{{- define "2hao-analyst.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{ include "2hao-analyst.selectorLabels" . }}
{{- end }}

{{/*
Create selector labels
*/}}
{{- define "2hao-analyst.selectorLabels" -}}
app.kubernetes.io/name: {{ include "2hao-analyst.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "2hao-analyst.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "2hao-analyst.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}