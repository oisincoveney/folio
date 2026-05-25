import os

import reflex as rx

config = rx.Config(
    app_name="folio",
    db_url=os.environ.get("DATABASE_URL", "postgresql://folio:folio@localhost:5432/folio"),
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