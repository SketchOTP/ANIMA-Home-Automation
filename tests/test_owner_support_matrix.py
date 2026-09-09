from scripts.verify_owner_support_matrix import verify


def test_declared_owner_support_matrix_matches_live_application_routes() -> None:
    result = verify()
    assert result["status"] == "PASSED"
    assert result["route_count"] >= 60
    assert result["domain_count"] >= 20
    assert result["invariants"]["ha_frontend_required"] is False
    assert result["invariants"]["browser_direct_ha"] is False
