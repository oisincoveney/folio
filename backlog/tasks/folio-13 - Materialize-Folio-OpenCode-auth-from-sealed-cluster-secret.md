---
id: FOLIO-13
title: Materialize Folio OpenCode auth from sealed cluster secret
status: Done
assignee:
  - Codex
created_date: '2026-05-25 13:48'
updated_date: '2026-05-25 13:59'
labels:
  - infra
  - deploy
  - ai-auth
dependencies: []
modified_files:
  - Dockerfile
  - docker-entrypoint.sh
  - /Users/oisin/dev/infra/mise.toml
  - /Users/oisin/dev/infra/k8s/manifests/folio/sealed-secrets/folio-secrets.yaml
  - /Users/oisin/dev/infra/k8s/manifests/folio/sealed-secrets/kustomization.yaml
priority: high
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Enable Folio pods to use the same local-to-cluster OpenCode auth pattern used by Autofix and RoboRev. Folio shells out to `opencode`, which expects credentials at `~/.local/share/opencode/auth.json`; production should be able to receive sealed `OPENCODE_AUTH_JSON` in `folio-secrets` and materialize it before the app process starts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Folio runtime image writes OPENCODE_AUTH_JSON to the OpenCode auth file path with restrictive permissions before starting the app.
- [x] #2 Folio still starts normally when OPENCODE_AUTH_JSON is absent, so local and unauthenticated smoke paths are not broken.
- [x] #3 Infra has Folio-specific mise tasks that seal the local OpenCode auth file into folio-secrets using the same kubeseal pattern as Autofix/RoboRev.
- [x] #4 Folio sealed-secrets kustomization refuses to point Argo at a partial folio-secrets manifest; the full sealing task updates it only after all required production keys are sealed.
- [x] #5 Relevant validation is run and documented.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a POSIX shell Docker entrypoint that, when OPENCODE_AUTH_JSON is present, writes it to $HOME/.local/share/opencode/auth.json with directory mode 0700 and file mode 0600, then execs the original command. If the env var is absent, it simply execs the command.
2. Install that entrypoint in the shared Docker syscommon stage so both base and runtime images can use it, without changing the existing CMDs.
3. Add infra Folio sealing tasks that avoid partial Secret manifests: one task bootstraps the full folio-secrets SealedSecret from required production env vars plus local OpenCode auth, and one task refreshes only OPENCODE_AUTH_JSON after the full manifest exists.
4. Keep the folio sealed-secrets kustomization from referencing a missing or partial folio-secrets.yaml; the full sealing task updates resources after it creates a complete sealed manifest.
5. Validate: shell syntax, Docker build, container entrypoint behavior with and without OPENCODE_AUTH_JSON, kustomize render for folio sealed secrets, YAML parse, and focused/project lint checks where relevant.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validation completed: `sh -n docker-entrypoint.sh`; `docker build --target runtime --build-arg REFLEX_API_URL=https://folio.momokaya.ee -t folio-review:auth-entrypoint .`; container smoke without OPENCODE_AUTH_JSON confirms no auth file is created; container smoke with OPENCODE_AUTH_JSON confirms file mode 0600 and directory mode 0700 owned by folio; `docker image inspect` confirms entrypoint/CMD/user; `mise tasks | rg 'secrets:folio'`; `mise run secrets:folio-auth:seal` fails safely when folio-secrets.yaml is absent; `mise run secrets:folio-secrets:seal` previously failed safely and listed missing production secret env vars; generated bootstrap credentials and ran `mise run secrets:folio-secrets:seal` successfully; `kubectl kustomize /Users/oisin/dev/infra/k8s/manifests/folio/sealed-secrets` renders the SealedSecret; Ruby YAML parse confirms kustomization and SealedSecret are valid YAML; Ruby key check confirms encryptedData contains DATABASE_URL, FOLIO_BUCKET_ACCESS_KEY, FOLIO_BUCKET_SECRET_KEY, OPENCODE_AUTH_JSON, and POSTGRES_PASSWORD; `kubeseal --validate` passes; `docker compose config --no-env-resolution`; `kubectl kustomize k8s/overlays/prod`; `mise run check`.

Generated the actual infra folio-secrets SealedSecret manifest with fresh bootstrap production credentials and local OpenCode auth, then included it from the folio sealed-secrets kustomization. Plaintext values were provided only to the sealing task process and were not written to the repo.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added Folio OpenCode auth materialization via Docker entrypoint and infra mise sealing tasks. Generated the actual `k8s/manifests/folio/sealed-secrets/folio-secrets.yaml` manifest with encrypted POSTGRES_PASSWORD, DATABASE_URL, FOLIO_BUCKET_ACCESS_KEY, FOLIO_BUCKET_SECRET_KEY, and OPENCODE_AUTH_JSON, and included it from the folio sealed-secrets kustomization. The production credentials were generated for bootstrap because the configured cluster has no existing folio namespace/Secret; plaintext was not written to the repo.
<!-- SECTION:FINAL_SUMMARY:END -->
