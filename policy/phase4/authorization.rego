package anima.authorization

import rego.v1

default decision := {
    "decision": "DENY",
    "reason_code": "POLICY_DEFAULT_DENY",
    "required_assurance": "AUTHENTICATED",
    "confirmation_required": false,
    "policy_version": "phase4-baseline-v1"
}

rank := data.assurance_rank[input.identity.assurance]
role_permitted := input.policy.role in {"owner", "resident"}
critical_uncertain := input.truth.critical_uncertain == true
confirmation_valid := input.confirmation.valid == true

decision := result if {
    input.action_intent.risk_class == "ADMIN_SYSTEM_PROHIBITED"
    result := {
        "decision": "DENY",
        "reason_code": "SYSTEM_CAPABILITY_PROHIBITED",
        "required_assurance": "ANONYMOUS",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "UNKNOWN"
    result := {
        "decision": "DENY",
        "reason_code": "UNKNOWN_RISK_FAIL_CLOSED",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "SECURITY_ACCESS_ACTION"
    rank < data.assurance_rank.STRONG_AUTHENTICATED
    result := {
        "decision": "REQUIRE_STRONGER_AUTH",
        "reason_code": "SECURITY_ACCESS_REQUIRES_STRONG_AUTH",
        "required_assurance": "STRONG_AUTHENTICATED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "SECURITY_ACCESS_ACTION"
    critical_uncertain
    result := {
        "decision": "DENY",
        "reason_code": "CRITICAL_TRUTH_UNCERTAIN",
        "required_assurance": "STRONG_AUTHENTICATED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "SECURITY_ACCESS_ACTION"
    role_permitted
    rank >= data.assurance_rank.STRONG_AUTHENTICATED
    result := {
        "decision": "ALLOW",
        "reason_code": "SECURITY_ACCESS_STRONG_AUTHORIZED",
        "required_assurance": "STRONG_AUTHENTICATED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "SECURITY_SECURE_ACTION"
    critical_uncertain
    result := {
        "decision": "DENY",
        "reason_code": "CRITICAL_TRUTH_UNCERTAIN",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "SECURITY_SECURE_ACTION"
    input.origin == "AUTONOMOUS_AGENT"
    input.policy.autonomy.security_secure_action
    result := {
        "decision": "ALLOW",
        "reason_code": "EXPLICIT_ANIMA_SECURE_AUTONOMY",
        "required_assurance": "ANONYMOUS",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "SECURITY_SECURE_ACTION"
    role_permitted
    rank >= data.assurance_rank.AUTHENTICATED
    result := {
        "decision": "ALLOW",
        "reason_code": "SECURE_ACTION_AUTHORIZED",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "LOW_RISK_HOME_CONTROL"
    input.origin == "AUTONOMOUS_AGENT"
    input.policy.autonomy.low_risk_home_control
    result := {
        "decision": "ALLOW",
        "reason_code": "EXPLICIT_ANIMA_LOW_RISK_AUTONOMY",
        "required_assurance": "ANONYMOUS",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "LOW_RISK_HOME_CONTROL"
    input.policy.role in {"owner", "resident", "guest"}
    rank >= data.assurance_rank.RECOGNIZED
    result := {
        "decision": "ALLOW",
        "reason_code": "LOW_RISK_HOME_CONTROL_AUTHORIZED",
        "required_assurance": "RECOGNIZED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "FINANCIAL_PURCHASE"
    confirmation_valid
    rank >= data.assurance_rank.AUTHENTICATED
    result := {
        "decision": "ALLOW",
        "reason_code": "EXPLICIT_PURCHASE_APPROVAL",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": true,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "FINANCIAL_PURCHASE"
    result := {
        "decision": "REQUIRE_CONFIRMATION",
        "reason_code": "PURCHASE_REQUIRES_EXPLICIT_APPROVAL",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": true,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "EXTERNAL_SIDE_EFFECT"
    input.action_intent.semantic_action == "notifications.send"
    input.origin == "DURABLE_SYSTEM_TASK"
    input.graph.notification_alert_authorized == true
    input.graph.notification_route_id != ""
    input.graph.alert_policy_id != ""
    result := {
        "decision": "ALLOW",
        "reason_code": "CONFIGURED_ALERT_NOTIFICATION",
        "required_assurance": "ANONYMOUS",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "EXTERNAL_SIDE_EFFECT"
    confirmation_valid
    result := {
        "decision": "ALLOW",
        "reason_code": "EXPLICIT_EXTERNAL_APPROVAL",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": true,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "EXTERNAL_SIDE_EFFECT"
    result := {
        "decision": "REQUIRE_CONFIRMATION",
        "reason_code": "EXTERNAL_SIDE_EFFECT_REQUIRES_CONFIRMATION",
        "required_assurance": "AUTHENTICATED",
        "confirmation_required": true,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "READ_ONLY"
    data.anonymous_read
    result := {
        "decision": "ALLOW",
        "reason_code": "READ_ONLY_POLICY",
        "required_assurance": "ANONYMOUS",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
} else := result if {
    input.action_intent.risk_class == "READ_ONLY"
    role_permitted
    result := {
        "decision": "ALLOW",
        "reason_code": "READ_ONLY_AUTHORIZED",
        "required_assurance": "CLAIMED",
        "confirmation_required": false,
        "policy_version": data.policy_version
    }
}
