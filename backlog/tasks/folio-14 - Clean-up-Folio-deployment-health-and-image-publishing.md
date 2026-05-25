---
id: FOLIO-14
title: Clean up Folio deployment health and image publishing
status: Done
assignee:
  - Codex
created_date: '2026-05-25 14:28'
updated_date: '2026-05-25 14:59'
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
- [x] #1 Argo health no longer leaves Folio Progressing solely because Traefik Ingress status has no load balancer address while TLS and backend are healthy.
- [x] #2 Folio has a committed repeatable image publish workflow/task that builds linux/amd64 runtime images with REFLEX_API_URL=https://folio.momokaya.ee and pushes to GHCR.
- [x] #3 Validation records live Argo/application state, HTTPS reachability, and image build/render checks.
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

The first GitHub Actions publish run queued indefinitely on `[linux, k8s-runner]` because this is a public personal repo and the org ARC runner did not pick it up. Cancelled run `26405964833` and changed the workflow to `ubuntu-latest`, which is already `linux/amd64` and can publish to `ghcr.io/oisincoveney/folio` with the repo `GITHUB_TOKEN`. Re-ran `actionlint .github/workflows/publish-image.yml`; it passed.

Validated the publishing follow-up locally: actionlint passed for publish-image.yml, Docker runtime build checks passed for linux/amd64, prod kustomize renders ghcr.io/oisincoveney/folio, and momokaya server-side dry-run accepts the overlay.

Added OCI source metadata to the runtime image so GHCR links the container package to oisincoveney/folio; a local publish of tag 'linked' confirmed the personal package is now repository-linked and no longer needs a separate GHCR_TOKEN for normal workflow writes.

Adjusted the publish workflow to commit the built commit SHA into k8s/overlays/prod/kustomization.yaml after pushing the image. This avoids relying on a mutable 'latest' tag for Argo rollouts while still publishing latest for manual/operator convenience.

Final validation: GitHub Actions run 26406464980 succeeded after adding repo secrets GHCR_USERNAME and GHCR_TOKEN. The workflow pushed ghcr.io/oisincoveney/folio:267a26eb35f0ce03a98b90356b55c7fe8d70b076 and latest to digest sha256:7d788501c7fb8e5deef37cb8102594d21dbb89bf648b8aa7b40b94b6575822d7, then committed bot deploy revision 917449be95a246ebae9c5e8886d1aa0aed38dbf1 to pin prod to that immutable image tag.

Live validation after Argo refresh: app-of-apps, argocd-config, folio, and folio-secrets are all Synced/Healthy. The folio Deployment has replicas=1 updated=1 ready=1 available=1, and the running pod folio-745bbf55d9-vfwdg uses image ghcr.io/oisincoveney/folio:267a26eb35f0ce03a98b90356b55c7fe8d70b076 with imageID ghcr.io/oisincoveney/folio@sha256:7d788501c7fb8e5deef37cb8102594d21dbb89bf648b8aa7b40b94b6575822d7, ready=true, restarts=0. curl -k -I https://folio.momokaya.ee/ returns HTTP/2 200.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Cleaned up Folio deployment health and image publishing. Infra now manages the Argo Traefik Ingress health customization, Folio publishes linux/amd64 runtime images through GitHub Actions and a matching mise task, and production is pinned to a workflow-built immutable image tag. Added GHCR_USERNAME and GHCR_TOKEN repository secrets so the workflow can push to the existing personal GHCR package. Verified Argo Synced/Healthy, the pod running the pinned digest with zero restarts, and HTTPS returning 200.
<!-- SECTION:FINAL_SUMMARY:END -->
