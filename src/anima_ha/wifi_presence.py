"""Private local-router Wi-Fi presence observation for the owner display.

This adapter is deliberately narrower than household Truth.  It reads the
owner-associated MACs from the server-side Graph, observes the local router's
neighbor table, and publishes only coarse person IDs plus last-seen times.
Absence is UNKNOWN, never proof of departure or identity.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance, EvidenceKind
from anima_ha.journal import PostgresEventJournal

MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
MAC_IN_TEXT_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{2}(?:[:-][0-9a-f]{2}){5})(?![0-9a-f])")
MAC_UNDERSCORE_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{2}(?:_[0-9a-f]{2}){5})(?!_[0-9a-f])")
DEFAULT_STATUS_PATH = Path(
    os.environ.get(
        "ANIMA_WIFI_PRESENCE_STATUS_PATH",
        "/var/lib/anima/provider-boundary/wifi-presence-status.json",
    )
)
# STALE still represents a learned L2 neighbor.  Treating it as absent makes
# idle phones flap between HOME and UNKNOWN even though they remain associated
# with Wi-Fi; a real departure is confirmed only after the entry disappears
# for the configured consecutive sweeps below.
ACTIVE_NEIGHBOR_STATES = frozenset({"REACHABLE", "STALE", "DELAY", "PROBE"})
MAX_SCAN_HOSTS = 254
DEFAULT_SCAN_INTERVAL = 60.0
NMAP_STATUS_MAX_AGE_SECONDS = 300
# Neighbor-table state can briefly disappear while a phone remains connected.
# Require two consecutive missing observations before changing the owner-facing
# state, so one transient LAN miss cannot look like a departure and return.
ABSENCE_CONFIRMATION_SWEEPS = 2
PRESENCE_EVENT_NAMESPACE = UUID("2b4f8e5d-b89a-4af8-899c-f2de0c10f1d2")


def _binding_fingerprint(macs: Iterable[str]) -> str:
    """Identify a MAC binding without persisting the private MAC values."""

    canonical = "\x1f".join(sorted(macs))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class WifiNeighbor:
    address: str
    mac: str
    state: str


@dataclass(frozen=True, slots=True)
class WifiPerson:
    household_id: str
    person_id: str
    macs: tuple[str, ...]


Runner = Callable[[Sequence[str], float], tuple[int, str]]


def normalize_mac(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold().replace("-", ":")
    return normalized if MAC_RE.fullmatch(normalized) else None


def tracker_macs(*values: object) -> set[str]:
    """Extract complete MAC identities from private HA tracker identifiers."""

    result: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        for match in MAC_IN_TEXT_RE.finditer(value):
            if (mac := normalize_mac(match.group(1))) is not None:
                result.add(mac)
        for match in MAC_UNDERSCORE_RE.finditer(value):
            if (mac := normalize_mac(match.group(1).replace("_", ":"))) is not None:
                result.add(mac)
    return result


def parse_neighbors(output: str, *, interface: str) -> list[WifiNeighbor]:
    """Parse only address/MAC/NUD state from ``ip neigh`` output."""

    result: list[WifiNeighbor] = []
    for line in output.splitlines():
        fields = line.split()
        try:
            mac_index = fields.index("lladdr") + 1
        except ValueError:
            continue
        if mac_index >= len(fields):
            continue
        mac = normalize_mac(fields[mac_index])
        state = fields[-1].upper() if fields else ""
        if mac is None:
            continue
        if any(token.rstrip(":") == "dev" for token in fields):
            try:
                if fields[fields.index("dev") + 1] != interface:
                    continue
            except (ValueError, IndexError):
                continue
        try:
            address = str(ipaddress.ip_address(fields[0]))
        except ValueError:
            continue
        result.append(WifiNeighbor(address, mac, state))
    return result


def default_interface(output: str) -> str | None:
    fields = output.split()
    try:
        return fields[fields.index("dev") + 1]
    except (ValueError, IndexError):
        return None


def ipv4_network(output: str, *, interface: str) -> ipaddress.IPv4Network | None:
    lines = output.splitlines()
    for line in lines:
        fields = line.split()
        if "inet" not in fields or not any(token.rstrip(":") == interface for token in fields):
            continue
        try:
            address = fields[fields.index("inet") + 1]
            network = ipaddress.ip_interface(address).network
        except (ValueError, IndexError):
            continue
        if (
            isinstance(network, ipaddress.IPv4Network)
            and network.num_addresses <= MAX_SCAN_HOSTS + 2
        ):
            return network
    return None


def project_wifi_presence(
    people: Iterable[WifiPerson],
    neighbors: Iterable[WifiNeighbor],
    *,
    now: datetime,
    previous: dict[str, dict[str, Any]] | None = None,
    router_presence: dict[str, datetime] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return sanitized per-person state; MACs never cross this boundary.

    ``last_seen_at`` is a freshness signal for the private observer and may
    advance on every matching sweep.  ``last_status_changed_at`` is the
    owner-facing transition signal: it advances only when the derived
    network-presence state changes.  A first observation has no known
    transition and therefore remains ``None`` until a real state change is
    observed.
    """

    current = now.astimezone(UTC)
    observed = {
        neighbor.mac: neighbor for neighbor in neighbors if neighbor.state in ACTIVE_NEIGHBOR_STATES
    }
    confirmed = router_presence or {}
    prior = previous or {}
    result: dict[str, dict[str, Any]] = {}
    for person in people:
        local_match = any(mac in observed for mac in person.macs)
        router_match = [confirmed[mac] for mac in person.macs if mac in confirmed]
        raw_match = local_match or bool(router_match)
        old = prior.get(person.person_id, {})
        last_seen = old.get("last_seen_at")
        last_status_changed = old.get("last_status_changed_at")
        previous_active = old.get("active")
        previous_absence_sweeps = old.get("absence_sweeps", 0)
        if type(previous_absence_sweeps) is not int or previous_absence_sweeps < 0:
            previous_absence_sweeps = 0
        absence_sweeps = 0
        match = raw_match
        if raw_match:
            # A detected phone immediately confirms a return and clears any
            # pending transient-miss debounce.
            absence_sweeps = 0
        elif previous_active is True:
            absence_sweeps = min(
                previous_absence_sweeps + 1,
                ABSENCE_CONFIRMATION_SWEEPS,
            )
            match = absence_sweeps < ABSENCE_CONFIRMATION_SWEEPS
        elif previous_active is False:
            # Keep the confirmed-departure marker stable while the phone
            # remains absent; it is diagnostic state, not a live ping time.
            absence_sweeps = min(
                previous_absence_sweeps,
                ABSENCE_CONFIRMATION_SWEEPS,
            )
        if isinstance(previous_active, bool) and previous_active != match:
            last_status_changed = current.isoformat()
        if raw_match:
            seen_times = [current] if local_match else []
            seen_times.extend(router_match)
            last_seen = max(seen_times).isoformat()
        result[person.person_id] = {
            "active": match,
            "status": "HOME" if match else "UNKNOWN",
            "last_seen_at": last_seen if isinstance(last_seen, str) else None,
            "last_status_changed_at": (
                last_status_changed if isinstance(last_status_changed, str) else None
            ),
            "absence_sweeps": absence_sweeps,
            "source": "LOCAL_ROUTER_MAC",
            "quality": "NETWORK_EVIDENCE_NOT_AUTHENTICATION",
        }
    return result


def presence_transition_event(
    person: WifiPerson,
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    now: datetime,
) -> EventEnvelope | None:
    """Create one deterministic event only for an effective presence edge."""

    before = previous.get("active")
    after = current.get("active")
    if type(before) is not bool or type(after) is not bool or before == after:
        return None
    changed_raw = current.get("last_status_changed_at")
    try:
        changed_at = datetime.fromisoformat(str(changed_raw))
        if changed_at.tzinfo is None or changed_at.utcoffset() is None:
            raise ValueError
        changed_at = changed_at.astimezone(UTC)
    except (TypeError, ValueError):
        changed_at = now.astimezone(UTC)
    transition = "RECONNECTED" if after else "DISCONNECTED"
    identity = f"wifi:{person.person_id}:{transition}:{changed_at.isoformat()}"
    return EventEnvelope.create(
        event_id=str(uuid5(PRESENCE_EVENT_NAMESPACE, identity)),
        event_type="household.presence.connection_changed",
        source="anima.household_presence",
        source_event_id=identity,
        subject_key=f"person/{person.person_id}",
        occurred_at=changed_at,
        recorded_at=now.astimezone(UTC),
        payload={
            "household_id": person.household_id,
            "person_id": person.person_id,
            "canonical_resource_id": person.person_id,
            "resource_id": person.person_id,
            "signal_kind": "ROUTER_WIFI",
            "transition": transition,
            "value": "HOME" if after else "UNKNOWN",
            "observed_at": changed_at.isoformat(),
            "is_authentication": False,
            "door_actor_verified": False,
            "evidence_basis": "ASSOCIATED_DEVICE_REPORTS",
            "time_basis": "LOCAL_ROUTER_OBSERVED",
            "external_content_trust": "EXTERNAL_UNTRUSTED",
        },
        evidence_kind=EvidenceKind.DIRECT,
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={
            "household_id": person.household_id,
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "presence_observer": "LOCAL_ROUTER_MAC",
            "synthetic": False,
        },
    )


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
        os.chmod(path, 0o640)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_previous(path: Path, *, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    try:
        if path.stat().st_mode & 0o007:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    usable = True
    if now is not None:
        try:
            observed = datetime.fromisoformat(str(value["observed_at"]))
            if (
                observed.tzinfo is None
                or value.get("state") not in {"READY", "DEGRADED"}
                or not timedelta(0) <= now.astimezone(UTC) - observed <= timedelta(seconds=120)
            ):
                usable = False
        except (KeyError, TypeError, ValueError, AttributeError):
            usable = False
    households = value.get("households") if isinstance(value, dict) else None
    if not isinstance(households, dict):
        return {}
    # The monitor loads one household at a time; callers select their scope.
    return {
        str(person_id): (
            dict(item)
            if usable
            else {
                **item,
                "active": None,
                "status": "UNKNOWN",
                "baseline_usable": False,
                "absence_sweeps": 0,
            }
        )
        for household in households.values()
        if isinstance(household, dict)
        for person_id, item in (household.get("people", {}) or {}).items()
        if isinstance(item, dict)
    }


class WifiPresenceMonitor:
    """Bounded host observer using the existing LAN neighbor table."""

    def __init__(
        self,
        database_url: str,
        *,
        status_path: Path = DEFAULT_STATUS_PATH,
        interval: float = DEFAULT_SCAN_INTERVAL,
        runner: Runner | None = None,
        clock: Callable[[], float] = time.time,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not database_url.strip():
            raise ValueError("database URL is required")
        if interval < 15 or interval > 300:
            raise ValueError("interval must be between 15 and 300 seconds")
        self.database_url = database_url
        self.status_path = status_path
        self.interval = interval
        self.event_sink = PostgresEventJournal(database_url)
        self.runner = runner or self._run_command
        self.clock = clock
        self.now = now or (lambda: datetime.now(UTC))
        self._last_sweep = 0.0
        self._known_addresses: dict[str, str] = {}

    @staticmethod
    def _run_command(argv: Sequence[str], timeout: float) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                list(argv),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 1, ""
        return completed.returncode, completed.stdout[:65_536]

    def _run(self, *argv: str, timeout: float = 8.0) -> tuple[int, str]:
        return self.runner(argv, timeout)

    def _people(self) -> list[WifiPerson]:
        query = """
            SELECT n.canonical_id, r.target_id AS household_id,
                   n.metadata->'wifi_macs' AS wifi_macs
            FROM anima_graph_nodes n
            JOIN anima_graph_relationships r
              ON r.source_id = n.canonical_id AND r.relationship_type = 'MEMBER_OF'
            WHERE n.kind = 'PERSON' AND n.retired_at IS NULL
        """
        with psycopg.connect(
            self.database_url, connect_timeout=5, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                result: list[WifiPerson] = []
                for row in cursor.fetchall():
                    raw_macs = row["wifi_macs"] or []
                    if not isinstance(raw_macs, list):
                        continue
                    macs = tuple(
                        sorted({mac for value in raw_macs if (mac := normalize_mac(value))})
                    )
                    household_id = row["household_id"]
                    if macs and household_id is not None:
                        result.append(
                            WifiPerson(
                                str(household_id),
                                str(row["canonical_id"]),
                                macs,
                            )
                        )
                return result

    def _nmap_presence(self, people: Iterable[WifiPerson]) -> dict[str, datetime]:
        """Read current HA nmap truth for configured MACs without publishing IDs."""

        configured = {mac for person in people for mac in person.macs}
        if not configured:
            return {}
        query = """
            SELECT i.instance_id, inv.external_id,
                   inv.metadata->>'original_name' AS original_name,
                   ts.status, ts.value, ts.last_observed_at, ts.last_received_at
            FROM anima_ha_provider_inventory inv
            JOIN anima_ha_instances i ON i.instance_id = inv.instance_id
            LEFT JOIN anima_truth_state ts
              ON ts.truth_key = 'provider/home_assistant/' || i.instance_id::text
                || '/entity/' || inv.external_id || '/state'
            WHERE inv.external_object_kind = 'entity'
              AND inv.present = true
              AND inv.metadata->>'platform' = 'nmap_tracker'
        """
        result: dict[str, datetime] = {}
        current = self.now().astimezone(UTC)
        with psycopg.connect(
            self.database_url, connect_timeout=5, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                for row in cursor.fetchall():
                    if row["status"] != "CURRENT/KNOWN" or row["value"] != "home":
                        continue
                    observed = row["last_observed_at"]
                    received = row["last_received_at"]
                    if not isinstance(observed, datetime) or not isinstance(received, datetime):
                        continue
                    observed = observed.astimezone(UTC)
                    received = received.astimezone(UTC)
                    if (
                        observed > current
                        or received > current
                        or observed > received
                        or current - received > timedelta(seconds=NMAP_STATUS_MAX_AGE_SECONDS)
                    ):
                        continue
                    for mac in tracker_macs(row["external_id"], row["original_name"]):
                        if mac not in configured:
                            continue
                        previous = result.get(mac)
                        if previous is None or observed > previous:
                            result[mac] = observed
        return result

    def _interface_and_network(self) -> tuple[str | None, ipaddress.IPv4Network | None]:
        _, route = self._run("/usr/sbin/ip", "route", "show", "default")
        interface = default_interface(route)
        if interface is None:
            return None, None
        _, address = self._run("/usr/sbin/ip", "-4", "addr", "show", "dev", interface)
        return interface, ipv4_network(address, interface=interface)

    def _neighbors(self, interface: str) -> list[WifiNeighbor]:
        code, output = self._run("/usr/sbin/ip", "neigh", "show", "dev", interface)
        if code != 0:
            raise ValueError("NEIGHBOR_COVERAGE_UNAVAILABLE")
        return parse_neighbors(output, interface=interface)

    def _probe(self, address: str, interface: str) -> None:
        self._run(
            "/usr/bin/ping",
            "-n",
            "-c",
            "1",
            "-W",
            "1",
            "-I",
            interface,
            address,
            timeout=2.5,
        )

    def _scan(self, interface: str, network: ipaddress.IPv4Network) -> None:
        # The host observer is intentionally bounded.  It never scans outside
        # the directly routed IPv4 subnet and never stores probe output.
        targets = [str(address) for address in network.hosts()]
        with ThreadPoolExecutor(max_workers=32, thread_name_prefix="anima-wifi") as pool:
            list(
                pool.map(
                    lambda address: self._probe(address, interface),
                    targets[:MAX_SCAN_HOSTS],
                )
            )

    def run_once(self) -> dict[str, Any]:
        people = self._people()
        interface, network = self._interface_and_network()
        if interface is None:
            return self._write({}, state="NOT_READY", reason="DEFAULT_ROUTE_UNAVAILABLE")

        now_mono = self.clock()
        for _person_id, address in tuple(self._known_addresses.items()):
            self._probe(address, interface)
        if network is not None and now_mono - self._last_sweep >= self.interval:
            self._scan(interface, network)
            self._last_sweep = now_mono
        try:
            neighbors = self._neighbors(interface)
        except ValueError:
            return self._write({}, state="NOT_READY", reason="NEIGHBOR_COVERAGE_UNAVAILABLE")
        for neighbor in neighbors:
            self._known_addresses[neighbor.mac] = neighbor.address
        router_presence = self._nmap_presence(people)
        by_household: dict[str, list[WifiPerson]] = {}
        for person in people:
            by_household.setdefault(person.household_id, []).append(person)
        old = _read_previous(self.status_path, now=self.now())
        previous_by_person: dict[str, dict[str, Any]] = {}
        for person in people:
            saved = old.get(person.person_id, {})
            # A MAC edit is configuration, not a physical presence edge.  A
            # fingerprint prevents the old device's state/timestamp from
            # being attributed to the newly associated device and establishes
            # a clean baseline on the next sweep.
            previous_by_person[person.person_id] = (
                saved
                if saved.get("binding_fingerprint") == _binding_fingerprint(person.macs)
                else {}
            )
        households = {
            household_id: {
                "people": project_wifi_presence(
                    members,
                    neighbors,
                    now=self.now(),
                    previous={
                        person.person_id: previous_by_person[person.person_id] for person in members
                    },
                    router_presence=router_presence,
                )
            }
            for household_id, members in by_household.items()
        }
        # The display file is not an event bus. Publish only effective HOME ↔
        # UNKNOWN transitions to the canonical Journal; Core's journal watcher
        # turns the committed event into the scoped SENTRY request.
        current_people = {
            person.person_id: households[person.household_id]["people"][person.person_id]
            for person in people
        }
        for person in people:
            current_people[person.person_id]["binding_fingerprint"] = _binding_fingerprint(
                person.macs
            )
            event = presence_transition_event(
                person,
                previous_by_person[person.person_id],
                current_people[person.person_id],
                now=self.now(),
            )
            if event is not None:
                self.event_sink.append(event)
        return self._write(
            households,
            state="READY" if network is not None else "DEGRADED",
            reason="LAN_NEIGHBOR_TABLE",
        )

    def _write(self, households: dict[str, Any], *, state: str, reason: str) -> dict[str, Any]:
        if state == "NOT_READY" and not households:
            # Coverage failure invalidates current baseline, NOT the owner's
            # genuine historical transition/last-seen/binding record.
            try:
                saved = json.loads(self.status_path.read_text(encoding="utf-8"))
                history = saved.get("households", {})
                if isinstance(history, dict):
                    for household_id, value in history.items():
                        if isinstance(value, dict) and isinstance(value.get("people"), dict):
                            households[household_id] = {
                                "people": {
                                    key: {
                                        **item,
                                        "active": None,
                                        "status": "UNKNOWN",
                                        "baseline_usable": False,
                                        "absence_sweeps": 0,
                                    }
                                    for key, item in value["people"].items()
                                    if isinstance(item, dict)
                                }
                            }
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        payload: dict[str, Any] = {
            "version": 1,
            "observed_at": self.now().astimezone(UTC).isoformat(),
            "state": state,
            "reason": reason,
            "households": households,
        }
        _atomic_json(self.status_path, payload)
        return payload


def main() -> int:
    database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
    if not database_url:
        user = os.environ.get("ANIMA_DB_USER", "anima")
        password = os.environ.get("ANIMA_DB_PASSWORD", "")
        database = os.environ.get("ANIMA_DB_NAME", "anima")
        port = os.environ.get("ANIMA_DB_PORT", "55434")
        database_url = f"postgresql://{user}:{password}@127.0.0.1:{port}/{database}"
    interval = float(os.environ.get("ANIMA_WIFI_PRESENCE_INTERVAL", "30"))
    monitor = WifiPresenceMonitor(database_url, interval=interval)
    while True:
        monitor.run_once()
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
