from __future__ import annotations

from datetime import UTC, datetime

from anima_ha.wifi_presence import (
    WifiNeighbor,
    WifiPerson,
    default_interface,
    ipv4_network,
    parse_neighbors,
    presence_transition_event,
    project_wifi_presence,
    tracker_macs,
)


def test_parse_neighbor_table_and_network_are_bounded() -> None:
    output = (
        "192.168.254.49 dev enp7s0 lladdr 00:d4:9e:9a:00:79 REACHABLE\n"
        "192.168.254.50 dev enp7s0 lladdr aa-bb-cc-dd-ee-ff STALE\n"
        "192.168.240.1 dev waydroid0 lladdr 00:11:22:33:44:55 REACHABLE\n"
    )
    neighbors = parse_neighbors(output, interface="enp7s0")
    assert neighbors == [
        WifiNeighbor("192.168.254.49", "00:d4:9e:9a:00:79", "REACHABLE"),
        WifiNeighbor("192.168.254.50", "aa:bb:cc:dd:ee:ff", "STALE"),
    ]
    assert default_interface("default via 192.168.254.254 dev enp7s0 proto dhcp") == "enp7s0"
    assert (
        str(
            ipv4_network(
                "2: enp7s0: <BROADCAST> inet 192.168.254.5/24 brd 192.168.254.255",
                interface="enp7s0",
            )
        )
        == "192.168.254.0/24"
    )


def test_match_is_private_and_absence_is_unknown_not_away() -> None:
    person = WifiPerson("household", "person-tym", ("aa:bb:cc:dd:ee:ff",))
    now = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)
    active = project_wifi_presence(
        [person],
        [WifiNeighbor("192.168.1.20", "aa:bb:cc:dd:ee:ff", "REACHABLE")],
        now=now,
    )
    assert active["person-tym"] == {
        "active": True,
        "status": "HOME",
        "last_seen_at": "2026-09-11T02:00:00+00:00",
        "last_status_changed_at": None,
        "absence_sweeps": 0,
        "source": "LOCAL_ROUTER_MAC",
        "quality": "NETWORK_EVIDENCE_NOT_AUTHENTICATION",
    }
    transient_miss = project_wifi_presence([person], [], now=now, previous=active)
    assert transient_miss["person-tym"]["active"] is True
    assert transient_miss["person-tym"]["status"] == "HOME"
    assert transient_miss["person-tym"]["last_seen_at"] == "2026-09-11T02:00:00+00:00"
    assert transient_miss["person-tym"]["last_status_changed_at"] is None
    assert transient_miss["person-tym"]["absence_sweeps"] == 1

    inactive = project_wifi_presence([person], [], now=now, previous=transient_miss)
    assert inactive["person-tym"]["active"] is False
    assert inactive["person-tym"]["status"] == "UNKNOWN"
    assert inactive["person-tym"]["last_seen_at"] == "2026-09-11T02:00:00+00:00"
    assert inactive["person-tym"]["last_status_changed_at"] == now.isoformat()
    assert inactive["person-tym"]["absence_sweeps"] == 2


def test_stale_neighbor_keeps_idle_phone_home_until_entry_disappears() -> None:
    person = WifiPerson("household", "person-tym", ("aa:bb:cc:dd:ee:ff",))
    now = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)
    active = project_wifi_presence(
        [person],
        [WifiNeighbor("192.168.1.20", "aa:bb:cc:dd:ee:ff", "REACHABLE")],
        now=now,
    )
    idle = project_wifi_presence(
        [person],
        [WifiNeighbor("192.168.1.20", "aa:bb:cc:dd:ee:ff", "STALE")],
        now=now.replace(minute=5),
        previous=active,
    )
    assert idle["person-tym"]["active"] is True
    assert idle["person-tym"]["last_status_changed_at"] is None
    assert idle["person-tym"]["last_seen_at"] == "2026-09-11T02:05:00+00:00"


def test_status_change_timestamp_ignores_same_state_pings_and_updates_on_rejoin() -> None:
    person = WifiPerson("household", "person-tym", ("aa:bb:cc:dd:ee:ff",))
    entered = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)
    active = project_wifi_presence(
        [person],
        [WifiNeighbor("192.168.1.20", "aa:bb:cc:dd:ee:ff", "REACHABLE")],
        now=entered,
    )
    active_later = project_wifi_presence(
        [person],
        [WifiNeighbor("192.168.1.20", "aa:bb:cc:dd:ee:ff", "REACHABLE")],
        now=entered.replace(minute=5),
        previous=active,
    )
    assert active_later["person-tym"]["last_seen_at"] == "2026-09-11T02:05:00+00:00"
    assert active_later["person-tym"]["last_status_changed_at"] is None
    assert active_later["person-tym"]["absence_sweeps"] == 0

    transient_miss = project_wifi_presence(
        [person],
        [],
        now=entered.replace(minute=6),
        previous=active_later,
    )
    assert transient_miss["person-tym"]["active"] is True
    assert transient_miss["person-tym"]["last_status_changed_at"] is None
    assert transient_miss["person-tym"]["absence_sweeps"] == 1

    left = project_wifi_presence(
        [person],
        [],
        now=entered.replace(minute=7),
        previous=transient_miss,
    )
    assert left["person-tym"]["last_status_changed_at"] == "2026-09-11T02:07:00+00:00"
    assert left["person-tym"]["absence_sweeps"] == 2
    still_away = project_wifi_presence(
        [person],
        [],
        now=entered.replace(minute=20),
        previous=left,
    )
    assert still_away["person-tym"]["last_status_changed_at"] == "2026-09-11T02:07:00+00:00"
    assert still_away["person-tym"]["absence_sweeps"] == 2

    rejoined = project_wifi_presence(
        [person],
        [WifiNeighbor("192.168.1.20", "aa:bb:cc:dd:ee:ff", "REACHABLE")],
        now=entered.replace(minute=21),
        previous=still_away,
    )
    assert rejoined["person-tym"]["last_status_changed_at"] == ("2026-09-11T02:21:00+00:00")


def test_tracker_macs_supports_private_ha_nmap_identifiers() -> None:
    assert tracker_macs(
        "device_tracker.nmap_tracker_aa_bb_cc_dd_ee_ff",
        "Nmap Tracker aa:bb:cc:dd:ee:ff",
    ) == {"aa:bb:cc:dd:ee:ff"}


def test_ha_router_truth_can_confirm_wifi_presence_without_local_neighbor() -> None:
    person = WifiPerson("household", "person-tym", ("aa:bb:cc:dd:ee:ff",))
    observed = datetime(2026, 9, 11, 2, 0, 30, tzinfo=UTC)
    result = project_wifi_presence(
        [person],
        [],
        now=datetime(2026, 9, 11, 2, 1, tzinfo=UTC),
        router_presence={"aa:bb:cc:dd:ee:ff": observed},
    )
    assert result["person-tym"]["active"] is True
    assert result["person-tym"]["status"] == "HOME"
    assert result["person-tym"]["last_seen_at"] == observed.isoformat()


def test_presence_transition_event_is_deterministic_and_contains_no_mac() -> None:
    person = WifiPerson("household", "person-tym", ("aa:bb:cc:dd:ee:ff",))
    now = datetime(2026, 9, 11, 2, 7, tzinfo=UTC)
    previous = {
        "active": True,
        "status": "HOME",
        "last_status_changed_at": "2026-09-11T02:00:00+00:00",
    }
    current = {
        "active": False,
        "status": "UNKNOWN",
        "last_status_changed_at": now.isoformat(),
    }
    first = presence_transition_event(person, previous, current, now=now)
    second = presence_transition_event(person, previous, current, now=now)
    assert first is not None and second is not None
    assert first.event_id == second.event_id
    assert first.source_event_id == second.source_event_id
    assert first.payload["transition"] == "DISCONNECTED"
    assert first.payload["canonical_resource_id"] == "person-tym"
    assert "aa:bb:cc:dd:ee:ff" not in str(first.to_dict())


def test_presence_transition_event_does_not_emit_for_baseline_or_same_state() -> None:
    person = WifiPerson("household", "person-tym", ("aa:bb:cc:dd:ee:ff",))
    now = datetime(2026, 9, 11, 2, 7, tzinfo=UTC)
    assert presence_transition_event(person, {}, {"active": True}, now=now) is None
    assert (
        presence_transition_event(
            person,
            {"active": True},
            {"active": True, "last_status_changed_at": now.isoformat()},
            now=now,
        )
        is None
    )
