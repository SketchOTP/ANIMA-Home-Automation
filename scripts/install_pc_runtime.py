"""Plan/install only the existing PC units and bounded client; never start them.

Default is a hash manifest. --apply is an operator deployment action, not a
recovery command. Existing credentials, request state, models and Graft are not
read or copied. Source remains in the preserved checkout; Docker image rebuild
is a separate reviewed step using Dockerfile.ui and .dockerignore.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LEGACY_PROJECT = "/home/sketch/Projects/ANIMA Home Automation"
UNITS = (
    "anima-pc.service",
    "anima-core.service",
    "anima-household-worker.service",
    "anima-wifi-presence.service",
)
CLIENT_FILES = (
    "anima_household_client.py",
    "anima_household_mcp.py",
    "codex_model.py",
    "household_worker.py",
    "sentry_turn.py",
    "scripts/launch_anima_household_mcp",
    "skills/anima-household-agent/SKILL.md",
)


def deployment_files(home: Path, project: Path = PROJECT) -> dict[Path, bytes]:
    files = {}
    for name in UNITS:
        text = (project / "deploy/systemd/user" / name).read_text()
        files[home / ".config/systemd/user" / name] = text.replace(
            LEGACY_PROJECT, str(project).replace("%", "%%")
        ).encode()
    client = project / "integrations/sentry/anima-household"
    for name in CLIENT_FILES:
        files[home / ".local/share/anima-household-client/runtime" / name] = (
            client / name
        ).read_bytes()
    return files


def install_files(files: dict[Path, bytes]) -> None:
    # Preflight every destination before replacing anything. No symlink-based
    # redirection, no directory sweep and no credential/config provisioning.
    for path in files:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("unsafe deployment destination")
        if any(parent.is_symlink() for parent in path.parents):
            raise ValueError("unsafe deployment parent")
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o700 if path.name == "launch_anima_household_mcp" else 0o600)
        temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    files = deployment_files(Path.home())
    manifest = [
        {"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in sorted(files.items())
    ]
    if args.apply:
        install_files(files)
    print(
        json.dumps(
            {
                "applied": args.apply,
                "files": manifest,
                "services_started": False,
                "daemon_reload_required": args.apply,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
