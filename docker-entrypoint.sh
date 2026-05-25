#!/bin/sh
set -eu

HOME="${HOME:-/home/folio}"
export HOME

write_secret_file() {
    path="$1"
    content="$2"
    dir="$(dirname "$path")"

    mkdir -p "$dir"
    chmod 700 "$dir"
    printf '%s' "$content" > "$path"
    chmod 600 "$path"
}

if [ -n "${OPENCODE_AUTH_JSON:-}" ]; then
    write_secret_file "$HOME/.local/share/opencode/auth.json" "$OPENCODE_AUTH_JSON"
fi

exec "$@"
