---
id: FOLIO-12
title: Make Reflex Docker production build deterministic
status: Done
assignee:
  - Codex
created_date: '2026-05-25 13:29'
updated_date: '2026-05-25 13:46'
labels:
  - infra
  - docker
  - deploy
dependencies: []
modified_files:
  - Dockerfile
  - docker-compose.yml
  - rxconfig.py
  - k8s/base/deployment.yaml
  - k8s/overlays/prod/kustomization.yaml
  - k8s/overlays/prod/deployment-patch.yaml
  - README.md
  - /Users/oisin/dev/infra/k8s/apps/platform/folio.yaml
  - /Users/oisin/dev/infra/k8s/apps/platform/folio-sealed.yaml
  - /Users/oisin/dev/infra/k8s/manifests/folio/sealed-secrets/kustomization.yaml
priority: high
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix the Docker/deployment setup so the prebuilt Reflex frontend cannot accidentally ship with localhost API/websocket URLs. Keep the local Tilt workflow on the base image target while making production builds require an explicit public REFLEX_API_URL at build time. Also reconcile the coupled /Users/oisin/dev/infra GitOps wiring for folio: the folio repo's prod overlay says secrets live in infra, but the infra repo currently has no folio Application or folio sealed-secret path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Production Docker runtime builds fail clearly when REFLEX_API_URL is not supplied as a build argument.
- [x] #2 Production Docker runtime builds with REFLEX_API_URL=https://folio.momokaya.ee bake the correct HTTPS/WSS endpoints into the generated Reflex frontend asset and sitemap.
- [x] #3 Local Docker Compose builds still work by supplying a localhost REFLEX_API_URL build argument.
- [x] #4 Tilt/local Kubernetes continues to build the base target for live-update development.
- [x] #5 Dockerfile and Kubernetes documentation comments no longer contradict the prebuilt-frontend runtime behavior.
- [x] #6 Production Kustomize output uses a deployable folio image tag and a pull policy appropriate for the mutable tag.
- [x] #7 Infra GitOps contains folio ArgoCD Application wiring that points at the folio production overlay and a pre-sync folio sealed-secrets Application path.
- [x] #8 Relevant build, render, and artifact validation commands have been run or any inability to run them is documented.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Update Dockerfile so the builder stage requires REFLEX_API_URL as a build arg, fails with a clear message if absent, and keeps the runtime image on Granian with correct __REFLEX_* flags.
2. Update docker-compose.yml to pass REFLEX_API_URL=http://localhost:3000 for local Compose builds.
3. Set rxconfig.py deploy_url from REFLEX_DEPLOY_URL or REFLEX_API_URL so the generated sitemap uses the same public URL as the frontend runtime asset.
4. Update folio Kubernetes/README comments so runtime REFLEX_API_URL is no longer described as the production frontend source of truth; document the required production build arg.
5. Keep Tiltfile target=base unchanged and verify the base target still builds.
6. Make the prod overlay render a deployable image reference for Argo by using ghcr.io/oisin-ee/folio:latest and setting production imagePullPolicy to Always for the app and migration init container.
7. Add infra ArgoCD Application manifests for folio: one Application pointing to https://github.com/oisin-ee/folio path k8s/overlays/prod, and one sync-wave -10 Application pointing to infra k8s/manifests/folio/sealed-secrets. Do not create or modify encrypted secret payloads.
8. Validate with Docker builds: base target succeeds; runtime without build arg fails; runtime with REFLEX_API_URL=https://folio.momokaya.ee succeeds and generated Reflex env asset/sitemap contains momokaya URLs and no localhost:3000. Validate Compose config/build and Kustomize/Argo YAML rendering where local tools permit.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented Docker fail-fast behavior for missing REFLEX_API_URL, production URL baking for Reflex env/sitemap via rxconfig.py deploy_url, docker-compose localhost build args, prod Kustomize latest image with Always pull policy, and infra ArgoCD folio/folio-secrets Applications plus an empty folio sealed-secrets kustomization path. Validation run: `docker build --target runtime` without REFLEX_API_URL fails with the intended clear error; `docker build --target base -t folio-review:base .` succeeds; `docker build --target runtime --build-arg REFLEX_API_URL=https://folio.momokaya.ee -t folio-review:runtime-prodarg .` succeeds; generated Reflex env asset and sitemap contain `https://folio.momokaya.ee` / `wss://folio.momokaya.ee`; `docker compose config --no-env-resolution` and `docker compose build folio` succeed; `kubectl kustomize k8s/overlays/prod` renders `ghcr.io/oisin-ee/folio:latest` with `imagePullPolicy: Always`; `kubectl kustomize /Users/oisin/dev/infra/k8s/manifests/folio/sealed-secrets` exits 0 with empty output; Ruby YAML parse validates the new infra Application YAML. `kubectl create --dry-run=client` could not validate Argo Application CRDs locally because the ArgoCD CRD is not installed in the current Kubernetes context. `mise run check`, `uv run ruff check rxconfig.py`, and `uv run python -m py_compile rxconfig.py` pass. Reflex export still warns about existing invalid icon tag `wand_2`, which is unrelated to this Docker/deploy fix.

Follow-up cleanup: replaced invalid Reflex/Lucide icon name `wand_2` with `wand_sparkles` in `folio/components/log_panel.py`. `uv run ruff check folio/components/log_panel.py` passes, and a fresh production Docker build with `REFLEX_API_URL=https://folio.momokaya.ee` no longer emits the invalid icon warning.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented deterministic Reflex production image builds, coupled GitOps wiring, and cleaned up the invalid Reflex icon warning.

Key changes:
- Docker runtime builds now require `REFLEX_API_URL`; missing production URL fails during the builder stage with a clear error instead of silently baking localhost into the frontend.
- `rxconfig.py` now derives `deploy_url` from `REFLEX_DEPLOY_URL` or `REFLEX_API_URL`, so both the Reflex env asset and sitemap use the production hostname during export.
- Docker Compose supplies `REFLEX_API_URL=http://localhost:3000` for local image builds, while Tilt remains on the `base` target for live-update development.
- Production Kustomize now renders `ghcr.io/oisin-ee/folio:latest` and sets `imagePullPolicy: Always` for both the app and db migration init container.
- Added infra ArgoCD Applications for `folio` and `folio-secrets`, plus the folio sealed-secrets kustomization path expected by the app repo.
- Replaced invalid `wand_2` icon with `wand_sparkles`.

Validation:
- Missing-arg runtime Docker build fails as intended.
- Base, production runtime, and Compose folio Docker builds pass.
- Production image artifact contains `https://folio.momokaya.ee` and `wss://folio.momokaya.ee` in the Reflex env asset and sitemap.
- Prod Kustomize render shows the correct image and pull policy.
- Project checks pass: `mise run check`, direct `rxconfig.py` ruff check, `py_compile`, and focused `log_panel.py` ruff check.
- Fresh production Docker build confirms the invalid icon warning is gone.

Notes:
- The actual encrypted `folio-secrets` and `ghcr-pull-secret` payloads are still not present in this work; only the GitOps Application/path wiring was added.
<!-- SECTION:FINAL_SUMMARY:END -->
