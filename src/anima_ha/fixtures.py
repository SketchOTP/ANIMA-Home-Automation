"""Deterministic synthetic commissioning data for simulator and integration tests."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.graph import (
    Alias,
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    ProviderReference,
    RelationshipType,
    TargetKind,
    TruthBinding,
)

_NAMESPACE = uuid5(NAMESPACE_URL, "https://anima-ha.invalid/fixtures/sample-household/v1")


def _id(name: str) -> UUID:
    return uuid5(_NAMESPACE, name)


def _node(name: str, kind: NodeKind, label: str, **metadata: object) -> CanonicalNode:
    security_sensitive = bool(metadata.pop("security_sensitive", False))
    return CanonicalNode(_id(name), kind, label, security_sensitive, dict(metadata))


def _rel(
    name: str, relationship_type: RelationshipType, source: str, target: str
) -> CanonicalRelationship:
    return CanonicalRelationship(
        _id(f"relationship/{name}"), relationship_type, _id(source), _id(target)
    )


def sample_household_document() -> CommissioningDocument:
    """Return a complete provider-independent synthetic home topology."""

    nodes = [
        _node("household", NodeKind.HOUSEHOLD, "Sample Household"),
        _node("property", NodeKind.PROPERTY, "Sample Property"),
        _node("outside", NodeKind.OUTSIDE, "Outside"),
        _node("house", NodeKind.BUILDING, "House"),
        _node("floor-1", NodeKind.FLOOR, "First Floor", floor_number=1),
        _node("floor-2", NodeKind.FLOOR, "Second Floor", floor_number=2),
        _node("foyer", NodeKind.ROOM, "Foyer"),
        _node("kitchen", NodeKind.ROOM, "Kitchen"),
        _node("living-room", NodeKind.ROOM, "Living Room"),
        _node("garage", NodeKind.ROOM, "Garage"),
        _node("bedroom", NodeKind.ROOM, "Bedroom"),
        _node("office", NodeKind.ROOM, "Office"),
        _node("front-entrance", NodeKind.ENTRANCE, "Front Door", security_sensitive=True),
        _node("garage-entrance", NodeKind.ENTRANCE, "Garage Door", security_sensitive=True),
        _node(
            "front-lock",
            NodeKind.RESOURCE,
            "Front Door Lock",
            security_sensitive=True,
            resource_type="lock",
        ),
        _node(
            "garage-door",
            NodeKind.RESOURCE,
            "Garage Door",
            security_sensitive=True,
            resource_type="opening",
        ),
        _node(
            "front-contact",
            NodeKind.SENSOR,
            "Front Door Contact",
            security_sensitive=True,
            sensor_type="contact",
        ),
        _node(
            "garage-contact",
            NodeKind.SENSOR,
            "Garage Door Contact",
            security_sensitive=True,
            sensor_type="contact",
        ),
        _node(
            "front-camera",
            NodeKind.RESOURCE,
            "Front Camera",
            security_sensitive=True,
            resource_type="camera",
        ),
        _node(
            "front-lock-state",
            NodeKind.CAPABILITY,
            "Lock State",
            capability_type="lock.state",
            readable=True,
        ),
        _node(
            "front-lock-lock",
            NodeKind.CAPABILITY,
            "Lock",
            capability_type="lock.lock",
            writable=True,
        ),
        _node(
            "front-lock-unlock",
            NodeKind.CAPABILITY,
            "Unlock",
            capability_type="lock.unlock",
            writable=True,
        ),
        _node(
            "garage-open",
            NodeKind.CAPABILITY,
            "Garage Open State",
            capability_type="opening.state",
            readable=True,
        ),
        _node("alex", NodeKind.PERSON, "Alex", semantic_role="owner"),
        _node("sam", NodeKind.PERSON, "Sam", semantic_role="resident"),
        _node("pippin", NodeKind.PET, "Pippin", species="dog"),
        _node("family-car", NodeKind.VEHICLE, "Family Car", vehicle_type="car"),
    ]
    relationships = [
        _rel("household-property", RelationshipType.CONTAINS, "household", "property"),
        _rel("property-outside", RelationshipType.CONTAINS, "property", "outside"),
        _rel("property-house", RelationshipType.CONTAINS, "property", "house"),
        _rel("house-floor-1", RelationshipType.CONTAINS, "house", "floor-1"),
        _rel("house-floor-2", RelationshipType.CONTAINS, "house", "floor-2"),
        _rel("floor-1-foyer", RelationshipType.CONTAINS, "floor-1", "foyer"),
        _rel("floor-1-kitchen", RelationshipType.CONTAINS, "floor-1", "kitchen"),
        _rel("floor-1-living", RelationshipType.CONTAINS, "floor-1", "living-room"),
        _rel("floor-1-garage", RelationshipType.CONTAINS, "floor-1", "garage"),
        _rel("floor-2-bedroom", RelationshipType.CONTAINS, "floor-2", "bedroom"),
        _rel("floor-2-office", RelationshipType.CONTAINS, "floor-2", "office"),
        _rel("front-outside", RelationshipType.CONNECTS, "front-entrance", "outside"),
        _rel("front-foyer", RelationshipType.CONNECTS, "front-entrance", "foyer"),
        _rel("garage-outside", RelationshipType.CONNECTS, "garage-entrance", "outside"),
        _rel("garage-garage", RelationshipType.CONNECTS, "garage-entrance", "garage"),
        _rel("front-lock-place", RelationshipType.INSTALLED_IN, "front-lock", "foyer"),
        _rel("garage-door-place", RelationshipType.INSTALLED_IN, "garage-door", "garage"),
        _rel("front-contact-place", RelationshipType.INSTALLED_IN, "front-contact", "foyer"),
        _rel("garage-contact-place", RelationshipType.INSTALLED_IN, "garage-contact", "garage"),
        _rel("front-camera-place", RelationshipType.INSTALLED_IN, "front-camera", "outside"),
        _rel("front-lock-state", RelationshipType.EXPOSES, "front-lock", "front-lock-state"),
        _rel("front-lock-lock", RelationshipType.EXPOSES, "front-lock", "front-lock-lock"),
        _rel("front-lock-unlock", RelationshipType.EXPOSES, "front-lock", "front-lock-unlock"),
        _rel("garage-open", RelationshipType.EXPOSES, "garage-door", "garage-open"),
        _rel("front-monitors", RelationshipType.MONITORS, "front-contact", "front-entrance"),
        _rel("garage-monitors", RelationshipType.MONITORS, "garage-contact", "garage-entrance"),
        _rel("camera-covers", RelationshipType.COVERS, "front-camera", "front-entrance"),
        _rel("alex-household", RelationshipType.MEMBER_OF, "alex", "household"),
        _rel("sam-household", RelationshipType.MEMBER_OF, "sam", "household"),
        _rel("pippin-household", RelationshipType.MEMBER_OF, "pippin", "household"),
        _rel("car-household", RelationshipType.MEMBER_OF, "family-car", "household"),
    ]
    aliases = [
        Alias(_id("alias/office"), "office", _id("office"), NodeKind.ROOM),
        Alias(_id("alias/my-office"), "my office", _id("office"), NodeKind.ROOM),
        Alias(_id("alias/study"), "study", _id("office"), NodeKind.ROOM),
        Alias(_id("alias/front"), "front entrance", _id("front-entrance"), NodeKind.ENTRANCE),
        Alias(_id("alias/garage"), "garage", _id("garage"), NodeKind.ROOM),
    ]
    provider_references = [
        ProviderReference(
            _id("provider/ha/front-device"),
            "home_assistant",
            "sample",
            "device",
            "ha-device-front",
            _id("front-lock"),
        ),
        ProviderReference(
            _id("provider/ha/front-entity"),
            "home_assistant",
            "sample",
            "entity",
            "lock.front_door",
            _id("front-lock-state"),
            TargetKind.CAPABILITY,
        ),
        ProviderReference(
            _id("provider/ha/front-lock-entity"),
            "home_assistant",
            "sample",
            "entity",
            "lock.front_door_control",
            _id("front-lock"),
        ),
        ProviderReference(
            _id("provider/ha/garage-device"),
            "home_assistant",
            "sample",
            "device",
            "ha-device-garage",
            _id("garage-door"),
        ),
        ProviderReference(
            _id("provider/other/front-lock"),
            "synthetic_provider",
            "sample",
            "resource",
            "front-lock-1",
            _id("front-lock"),
        ),
    ]
    truth_bindings = [
        TruthBinding(
            _id("binding/alex-home"),
            _id("alex"),
            TargetKind.NODE,
            f"presence/person/{_id('alex')}/home",
            "presence.home",
        ),
        TruthBinding(
            _id("binding/sam-home"),
            _id("sam"),
            TargetKind.NODE,
            f"presence/person/{_id('sam')}/home",
            "presence.home",
        ),
        TruthBinding(
            _id("binding/front-contact"),
            _id("front-entrance"),
            TargetKind.NODE,
            "opening/front-entrance/contact",
            "opening.contact",
        ),
        TruthBinding(
            _id("binding/lock-state"),
            _id("front-lock-state"),
            TargetKind.CAPABILITY,
            "security/front-lock/state",
            "lock.state",
        ),
    ]
    document = CommissioningDocument(
        1,
        tuple(nodes),
        tuple(relationships),
        tuple(aliases),
        tuple(provider_references),
        tuple(truth_bindings),
    )
    return document
