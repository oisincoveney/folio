# Folio

Folio is a Reflex app with Postgres and Minio dependencies. The Kubernetes
manifests under `k8s/` are intended to be exercised locally before deploying
changes to the `momokaya` cluster.

## Local Kubernetes with Tilt

Use Tilt against a separate local k3d cluster. Do not use the `momokaya`
context for the local development loop.

Prerequisites:

- Docker
- `mise`

Install pinned project tools:

```sh
mise install
```

Create the local cluster once:

```sh
mise run k8s:create
mise run k8s:kubeconfig
```

Start the local Kubernetes environment:

```sh
mise dev
```

Tilt will build the `folio` image, deploy Postgres, Minio, and the app, then
watch for local file changes. Python app and migration files are synced into
the running container with Tilt live update. Dependency and image changes such
as `pyproject.toml`, `uv.lock`, or `Dockerfile` trigger a full image rebuild.

Local URLs:

- App frontend: <http://localhost:3000>
- App backend: <http://localhost:8000>
- Minio console: <http://localhost:9001>

The `Tiltfile` only allows the `k3d-folio-local` Kubernetes context. If
your global `kubectl` context is `momokaya`, leave it alone. The mise tasks set
`KUBECONFIG=k8s/local/folio-local.kubeconfig` and pass `--context k3d-folio-local`
explicitly, so local development does not switch your global kubeconfig context.

Run a one-shot local Kubernetes validation:

```sh
mise run dev:ci
```

## Production Image Build

The production image prebuilds the Reflex frontend. Pass the public API URL at
build time so the generated browser asset contains the correct HTTPS and WSS
endpoints:

```sh
docker build \
  --target runtime \
  --build-arg REFLEX_API_URL=https://folio.momokaya.ee \
  -t ghcr.io/oisin-ee/folio:latest .
```

Do not rely on the Kubernetes runtime configmap to set this value for
production. Once `reflex export` has run, the frontend URL is baked into the
image.

## Other Development Commands

Run Reflex directly on the host, assuming Postgres and Minio-compatible
environment variables are already configured:

```sh
mise run dev:local
```

Delete the local k3d cluster:

```sh
mise run k8s:delete
```

Run checks:

```sh
mise run check
mise run test
```
