from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SENTRY = ROOT.parent / "SENTRY"


def ordering_graph(paths: dict[Path, str]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path, text in paths.items():
        graph.setdefault(path.name, set())
        for line in text.splitlines():
            if line.startswith("After="):
                graph[path.name].update(line.partition("=")[2].split())
            if line.startswith("WantedBy="):
                for target in line.partition("=")[2].split():
                    # Targets' DefaultDependencies adds After their wanted units.
                    graph.setdefault(target, set()).add(path.name)
    return graph


def has_cycle(graph: dict[str, set[str]]) -> bool:
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in visited:
            return False
        active.add(node)
        if any(visit(dependency) for dependency in graph.get(node, ())):
            return True
        active.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


@pytest.mark.skipif(not SENTRY.is_dir(), reason="integrated graph needs sibling SENTRY checkout")
def test_cross_repository_startup_order_is_acyclic_and_old_edge_reproduces_cycle() -> None:
    # Required integrated qualification uses both local repos, not Graft cache.
    paths = {
        path: path.read_text()
        for root in (ROOT, SENTRY)
        for path in (root / "deploy/systemd/user").glob("*.service")
    }
    assert SENTRY.is_dir(), "integrated startup graph requires the SENTRY checkout"
    assert paths
    graph = ordering_graph(paths)
    assert not has_cycle(graph)
    assert "anima-pc.service" in graph["anima-core.service"]
    assert "anima-core.service" in graph["anima-household-worker.service"]
    for name in ("anima-pc.service", "sentry-voice.service", "sentry-voice-supervisor.service"):
        broken = {key: set(value) for key, value in graph.items()}
        broken[name].add("default.target")
        assert has_cycle(broken)
