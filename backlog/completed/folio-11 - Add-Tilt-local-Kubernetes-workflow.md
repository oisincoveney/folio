---
id: FOLIO-11
title: Add Tilt local Kubernetes workflow
status: Done
assignee:
  - Codex
created_date: '2026-05-22 21:18'
updated_date: '2026-05-22 21:54'
labels:
  - dev-infra
  - local-dev
dependencies: []
modified_files:
  - Tiltfile
  - README.md
  - mise.toml
  - Dockerfile
  - folio/parse.py
  - tests/test_parse.py
  - k8s/configmap.yaml
  - k8s/secret.yaml
  - k8s/deployment.yaml
  - k8s/service.yaml
  - k8s/postgres/statefulset.yaml
  - k8s/local/k3d.yaml
  - k8s/local/.gitignore
  - k8s/minio/pvc.yaml
  - k8s/minio/service.yaml
  - k8s/minio/statefulset.yaml
priority: medium
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a Tilt-based local development workflow for the existing Kubernetes manifests so folio can be built, deployed, port-forwarded, and exercised locally before promoting changes to the momokaya cluster. The implementation should build on the current Dockerfile, k8s manifests, and existing k3d/Skaffold assumptions where appropriate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A developer can start the local Kubernetes workflow with a documented command.
- [x] #2 Tilt builds the folio image, deploys Postgres, Minio, and the folio app using the local manifests, and exposes the app and Minio console on localhost.
- [x] #3 Local source edits to the app trigger a fast rebuild or live update path that is appropriate for this Python/Reflex app.
- [x] #4 The workflow documentation names required local tools and cluster assumptions, including how this differs from deploying to the momokaya cluster.
- [x] #5 Relevant static validation or dry-run checks are performed and recorded.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Added a Tiltfile for local Kubernetes development that builds the existing `folio` Docker image, applies the existing Kubernetes manifests, groups dependent resources, and exposes frontend/backend/Minio ports locally.
2. Configured the Tiltfile to allow only the explicit local k3d context (`k3d-folio-local`) for this workflow; the `momokaya` cluster remains outside the local dev loop.
3. Added Tilt to `mise.toml`, made `mise dev` run Tilt, and removed the previous Skaffold configuration/tooling so Tilt is the only Kubernetes local-dev workflow.
4. Added README documentation for prerequisites, registry-enabled local cluster creation, startup commands, exposed URLs, and the momokaya boundary.
5. Validated Tiltfile evaluation, Kubernetes manifest dry-run, full Tilt CI deployment to `k3d-folio-local`, service responses on ports 3000 and 8000, and the project `mise run check` task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Initial context gathered: repository already has Dockerfile, k8s manifests, skaffold.yaml, and mise dev tasks oriented around k3d/local Kubernetes. No current kubectl context is configured and no k3d clusters are currently present on this machine, so full deploy validation will require creating/selecting a local cluster.

User clarified that `momokaya` is the Kubernetes cluster. The Tilt workflow should document and, where possible, guard the intended cluster/context rather than describe momokaya as a separate deployment system.

User confirmed Tilt should deploy to a separate local cluster, not directly to the `momokaya` cluster. The implementation should include local-context guidance/guards to reduce accidental deployment to momokaya during local development.

Scope update from user: remove Skaffold instead of keeping it as a fallback.

Validation completed: `mise exec -- tilt alpha tiltfile-result --context k3d-folio-local` succeeded; `kubectl apply --dry-run=client ...` succeeded against the local k3d cluster; `mise exec -- tilt ci --context k3d-folio-local --timeout=8m --port=0` succeeded with all workloads healthy; manual port-forward checks returned HTTP 200 for `http://127.0.0.1:3000` and `http://127.0.0.1:8000`; `mise run check` passed. During validation, k3d without a local registry caused Tilt to try pushing to Docker Hub, so the documented cluster creation now includes `--registry-create folio-registry:127.0.0.1:5001`. Reflex prod runs full-stack on a single port, so the Kubernetes service keeps port 8000 as a local alias that targets container port 3000, and readiness probes port 3000.

User requested a revision: local development should not change global kubectl context/config, and the documented workflow should use mise commands only.

Revision completed: local development no longer requires or changes global kubectl context. Added pinned `k3d` and `kubectl` tools to mise, `k8s:create` generates `.kube/folio-local.yaml` with `--kubeconfig-update-default=false`, and `dev`, `dev:ci`, and `k8s:dry-run` set `KUBECONFIG=.kube/folio-local.yaml` plus explicit `--context k3d-folio-local`. Removed the previously-created `k3d-folio-local` context/cluster/user from the global kubeconfig after generating the project-local kubeconfig. Validation rerun using mise-only commands: `mise run k8s:dry-run`, `mise run dev:ci`, and `mise run check` all passed. `kubectl config get-contexts` now shows no global contexts on this machine.

Replaced imperative local setup with declarative k3d config plus mise tasks that always pass a project-local KUBECONFIG and explicit k3d context.

Removed Skaffold from the local workflow; Tilt now builds/deploys the app with Postgres and MinIO dependencies to the local k3d cluster.

Fixed local container runtime issue by installing opencode in the image and preventing missing/timeout opencode calls from crashing model loading.

Removed the optional directory-level opencode auth mount after it made OpenCode's data directory read-only.

Rotated the local Postgres dev password away from the app name to stop Tilt redacting normal folio log text while preserving existing PVC data.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added a Tilt + k3d local Kubernetes workflow driven by mise tasks and project-local kubeconfig. Removed Skaffold, added persistent local Postgres/MinIO manifests, fixed the container's OpenCode runtime path, and validated the stack with Tilt CI, lint/typecheck, manifest dry-run, and targeted parse tests.
<!-- SECTION:FINAL_SUMMARY:END -->
