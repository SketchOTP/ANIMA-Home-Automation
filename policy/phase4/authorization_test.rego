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

test_admin_is_always_denied if {
    result := authorization.decision with input as base with input.action_intent as {"risk_class": "ADMIN_SYSTEM_PROHIBITED"}
    result.decision == "DENY"
}
