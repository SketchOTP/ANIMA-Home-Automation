"""Isolated browser fixture: real Core API/filesystem, synthetic policy and login.

No production environment, database, vault or provider is loaded. This is test
infrastructure, not a knowledge-curation script. The owner service is untouched.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


def main() -> None:
    os.environ.clear()
    os.environ["ANIMA_UI_TEST_AUTH"] = "1"
    import uvicorn

    from anima_ha.knowledge import KNOWLEDGE_MANIFEST, KnowledgeConfig, KnowledgeNativePlugin
    from anima_ha.plugins import NativeRuntime, PluginManager
    from anima_ha.policy import PolicyService
    from anima_ha.ui_api import UIConfig, UIService, create_app
    from anima_ha.ui_runtime import CoreUICommandGateway

    class AllowSyntheticPolicy:
        def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
            return {
                "decision": "ALLOW",
                "reason_code": "SYNTHETIC_BROWSER_FIXTURE",
                "policy_version": "test-only",
            }

    with tempfile.TemporaryDirectory(prefix="anima-knowledge-browser-") as temporary:
        managed = Path(temporary) / "ANIMA"
        managed.mkdir(mode=0o700)
        manager = PluginManager()
        manager.register(
            KNOWLEDGE_MANIFEST, NativeRuntime(KnowledgeNativePlugin(KnowledgeConfig(managed)))
        )
        manager.enable(KNOWLEDGE_MANIFEST.plugin_id)
        commands = CoreUICommandGateway(manager, PolicyService(AllowSyntheticPolicy()))
        app = create_app(
            UIService(
                config=UIConfig(test_auth_enabled=True, static_dir=Path(sys.argv[1])),
                commands=commands,
            )
        )
        with socket.socket() as bound:
            bound.bind(("127.0.0.1", 0))
            bound.listen(128)
            server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="error"))
            timer = threading.Timer(900, lambda: setattr(server, "should_exit", True))
            timer.daemon = True
            timer.start()
            print(f"SYNTHETIC_FIXTURE pid={os.getpid()} port={bound.getsockname()[1]}", flush=True)
            try:
                server.run(sockets=[bound])
            finally:
                timer.cancel()


if __name__ == "__main__":
    main()
