"""Start API, worker and frontend after installation. Ctrl+C stops all children."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
backend, frontend = root / "backend", root / "frontend"
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend, check=True
)
commands = [
    (
        backend,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
    ),
    (backend, [sys.executable, "-m", "app.worker"]),
    (frontend, ["npm.cmd" if os.name == "nt" else "npm", "run", "dev"]),
]
children = []
try:
    for folder, command in commands:
        children.append(subprocess.Popen(command, cwd=folder))
    print("Open http://localhost:5173. Ctrl+C stops all services.", flush=True)
    while all(child.poll() is None for child in children):
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
