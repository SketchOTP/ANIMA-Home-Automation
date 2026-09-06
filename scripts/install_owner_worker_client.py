"""Copy only the scoped service-client credential over the operator's SSH link.

No HA/DB/OPA credentials, auth store, or provider transcripts are read. Run this
operator-only installer on the workstation; it is not an ANIMA/MCP capability.
"""

from __future__ import annotations

import argparse
import hmac
import os
import shlex
import stat
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = args.output.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
        raise SystemExit("CLIENT_DIRECTORY_UNSAFE")
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "atlas-laptop",
            shlex.join(
                [
                    "docker",
                    "exec",
                    "anima-ha-ui-1",
                    "python",
                    "-c",
                    "import sys; from pathlib import Path; "
                    "sys.stdout.write(Path('/var/lib/anima/provider-boundary/client.token').read_text())",
                ]
            ),
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    token = result.stdout.strip()
    if result.returncode or not 32 <= len(token) <= 256 or b"\n" in token:
        raise SystemExit("CLIENT_CREDENTIAL_TRANSFER_FAILED")
    if args.output.exists() or args.output.is_symlink():
        info = args.output.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise SystemExit("CLIENT_FILE_UNSAFE")
        if not hmac.compare_digest(args.output.read_bytes().strip(), token):
            raise SystemExit("CLIENT_ROTATION_REQUIRES_EXPLICIT_PROVISIONING")
    else:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(token)
            stream.flush()
            os.fsync(stream.fileno())
    print("SCOPED_SERVICE_CLIENT_PROVISIONED")


if __name__ == "__main__":
    main()
