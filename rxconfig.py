"""Reflex configuration for Folio."""

import os

import reflex as rx

config = rx.Config(
    app_name="folio",
    db_url=os.environ.get("DATABASE_URL", "postgresql://folio:folio@localhost:5432/folio"),
    deploy_url=os.environ.get(
        "REFLEX_DEPLOY_URL",
        os.environ.get("REFLEX_API_URL", "http://localhost:3000"),
    ),
    # The cluster-sync dev loop serves `reflex run --env dev` (Vite) behind the
    # momokaya ingress at folio-dev.momokaya.ee. Vite 6 rejects requests with a
    # foreign Host header (HTTP 403) unless the host is in server.allowedHosts.
    # Allowlist the dev ingress host (scoped, not allow-all). Production serves a
    # compiled build, so this is inert there. Override via FOLIO_DEV_ALLOWED_HOSTS
    # (comma-separated) for other ingress hosts.
    vite_allowed_hosts=[
        h.strip()
        for h in os.environ.get(
            "FOLIO_DEV_ALLOWED_HOSTS", "folio-dev.momokaya.ee"
        ).split(",")
        if h.strip()
    ],
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                accent_color="indigo",
                gray_color="slate",
                radius="small",
            ),
        ),
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
