---
id: FOLIO-14
title: Clean up Folio deployment health and image publishing
status: In Progress
assignee:
  - Codex
created_date: '2026-05-25 14:28'
updated_date: '2026-05-25 14:38'
labels:
  - infra
  - deploy
  - ci
dependencies: []
priority: medium
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix the remaining Folio deployment cleanup items after the production rollout: make Argo health reporting reflect the cluster's Traefik ingress pattern instead of leaving apps Progressing, and add a repeatable CI/local image publishing path for the Folio amd64 production image.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Argo health no longer leaves Folio Progressing solely because Traefik Ingress status has no load balancer address while TLS and backend are healthy.
- [ ] #2 Folio has a committed repeatable image publish workflow/task that builds linux/amd64 runtime images with REFLEX_API_URL=https://folio.momokaya.ee and pushes to GHCR.
- [ ] #3 Validation records live Argo/application state, HTTPS reachability, and image build/render checks.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a Folio `image:publish` mise task mirroring the cluster-compatible amd64 build path used in the other app repos.
2. Add a GitHub Actions publish workflow on the repo's ARC runner labels that builds the Docker `runtime` target for `linux/amd64`, passes `REFLEX_API_URL=https://folio.momokaya.ee`, and pushes `latest` plus commit-SHA tags to GHCR.
3. Align the canonical image namespace with the actual Folio GitHub repo owner (`ghcr.io/oisincoveney/folio`) so the workflow can publish with the repo `GITHUB_TOKEN` instead of requiring a broad cross-org PAT.
4. Add GitOps-managed Argo CD config for a custom Traefik Ingress health rule, preserving the existing `argocd-cm` data while treating `ingressClassName: traefik` resources as healthy even when `status.loadBalancer` is intentionally blank.
5. Commit/push Folio and infra changes, reconcile Argo, and verify the live app remains reachable with Folio reporting Healthy.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added Folio image publishing support and switched the canonical image from the temporary private org package `ghcr.io/oisin-ee/folio` to `ghcr.io/oisincoveney/folio`, matching the actual GitHub repo owner so Actions can publish with `GITHUB_TOKEN`. Added `.github/workflows/publish-image.yml`, `.github/actionlint.yaml`, and `mise run image:publish`. Published a bootstrap amd64 runtime image with `TAG=bootstrap mise run image:publish`; both `bootstrap` and `latest` resolve to `sha256:0141313c955c522a26cda937c92afe933269e7910396f9bb82a8cc420885e6e0`. Validation so far: `mise run check` passed, `actionlint .github/workflows/publish-image.yml` passed, `docker buildx build --check --platform linux/amd64 --target runtime --build-arg REFLEX_API_URL=https://folio.momokaya.ee .` passed, `kubectl kustomize k8s/overlays/prod` renders `ghcr.io/oisincoveney/folio:latest` with `imagePullPolicy: Always`, and server dry-run apply of the Folio prod overlay passed.
<!-- SECTION:NOTES:END -->
