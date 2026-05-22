import os

import reflex as rx

config = rx.Config(
    app_name="folio",
    db_url=os.environ.get("DATABASE_URL", "postgresql://folio:folio@localhost:5432/folio"),
    plugins=[
        rx.plugins.RadixThemesPlugin(),
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)