LOCAL_CONTEXT = "k3d-folio-local"

allow_k8s_contexts(LOCAL_CONTEXT)

docker_build(
    "folio",
    ".",
    dockerfile="Dockerfile",
    target="base",
    live_update=[
        fall_back_on("Dockerfile"),
        fall_back_on("pyproject.toml"),
        fall_back_on("uv.lock"),
        sync("./folio", "/app/folio"),
        sync("./alembic", "/app/alembic"),
        sync("./alembic.ini", "/app/alembic.ini"),
        sync("./rxconfig.py", "/app/rxconfig.py"),
    ],
)

k8s_yaml(kustomize("k8s/overlays/local"))

k8s_resource(
    "postgres",
    labels=["data"],
)

k8s_resource(
    "minio",
    port_forwards=["9001:9001"],
    labels=["data"],
)

k8s_resource(
    "minio-create-bucket",
    resource_deps=["minio"],
    labels=["setup"],
)

k8s_resource(
    "folio",
    port_forwards=["3000:3000", "8000:8000"],
    resource_deps=["postgres", "minio-create-bucket"],
    labels=["app"],
)
