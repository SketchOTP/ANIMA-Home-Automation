package anima.authorization_test

import rego.v1
import data.anima.authorization

base := {
    "identity": {"assurance": "AUTHENTICATED", "principal_id": "person-1"},
    "origin": "DIRECT_USER",
    "policy": {
        "role": "resident",
        "autonomy": {"low_risk_home_control": true, "security_secure_action": true}
    },
    "truth": {"critical_uncertain": false},
    "confirmation": {"valid": false}
}

test_read_is_allowed_without_identity if {
    result := authorization.decision with input as base with input.action_intent as {"risk_class": "READ_ONLY"}
    result.decision == "ALLOW"
}

test_unlock_requires_strong_auth if {
    result := authorization.decision with input as base with input.identity as {"assurance": "RECOGNIZED", "principal_id": "person-1"} with input.action_intent as {"risk_class": "SECURITY_ACCESS_ACTION"}
    result.decision == "REQUIRE_STRONGER_AUTH"
}

test_external_side_effect_requires_confirmation if {
    result := authorization.decision with input as base with input.action_intent as {"risk_class": "EXTERNAL_SIDE_EFFECT"}
    result.decision == "REQUIRE_CONFIRMATION"
}

test_configured_alert_notification_is_explicitly_authorized if {
    result := authorization.decision with input as base with input.origin as "DURABLE_SYSTEM_TASK" with input.graph as {
        "notification_alert_authorized": true,
        "notification_route_id": "route-1",
        "alert_policy_id": "policy-1"
    } with input.action_intent as {
        "risk_class": "EXTERNAL_SIDE_EFFECT",
        "semantic_action": "notifications.send"
    }
    result.decision == "ALLOW"
    result.reason_code == "CONFIGURED_ALERT_NOTIFICATION"
}

test_unbound_system_notification_still_requires_confirmation if {
    result := authorization.decision with input as base with input.origin as "DURABLE_SYSTEM_TASK" with input.action_intent as {
        "risk_class": "EXTERNAL_SIDE_EFFECT",
        "semantic_action": "notifications.send"
    }
    result.decision == "REQUIRE_CONFIRMATION"
}

test_admin_is_always_denied if {
    result := authorization.decision with input as base with input.action_intent as {"risk_class": "ADMIN_SYSTEM_PROHIBITED"}
    result.decision == "DENY"
}

test_guest_can_use_low_risk_control if {
    result := authorization.decision with input as base with input.policy.role as "guest" with input.action_intent as {"risk_class": "LOW_RISK_HOME_CONTROL"}
    result.decision == "ALLOW"
}

test_guest_cannot_use_secure_action if {
    result := authorization.decision with input as base with input.policy.role as "guest" with input.identity as {"assurance": "AUTHENTICATED", "principal_id": "person-1"} with input.action_intent as {"risk_class": "SECURITY_SECURE_ACTION"}
    result.decision == "DENY"
}

test_restricted_cannot_mutate if {
    result := authorization.decision with input as base with input.policy.role as "restricted" with input.action_intent as {"risk_class": "LOW_RISK_HOME_CONTROL"}
    result.decision == "DENY"
}
