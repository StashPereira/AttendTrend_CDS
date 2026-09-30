"""Generate a new local database credential without bundling any credentials."""

import os
import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / ".env"
if path.exists():
    raise SystemExit(
        ".env already exists. Keep it, or remove it explicitly to generate a new configuration."
    )
content = f"POSTGRES_PASSWORD={secrets.token_hex(32)}\nWEB_PORT=8080\nENVIRONMENT=development\nCOOKIE_SECURE=false\nALLOWED_ORIGINS=http://localhost:8080\n"
with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
    file.write(content)
print("Configuration created. Run: docker compose up --build")
