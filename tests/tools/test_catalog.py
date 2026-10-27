"""Catalog mechanics: registration gate, request building, entries."""

import pytest

from molchat_agent.tools import (
    Capability,
    EpistemicClass,
    FieldSpec,
    PlanValidationError,
    capability,
    catalog,
    register,
)

EXPECTED = {
    "list_targets", "check_preflight", "list_evaluations",
    "evaluation_status", "get_docking_proposal", "approve_docking_proposal",
    "list_engines", "get_evaluation_result", "get_interactions",
    "get_gnn_attention", "stream_evaluation", "cancel_evaluation",
    "batch_status", "cancel_batch", "export_batch", "get_ai_report",
    "stream_ai_report", "get_case_dossier", "get_sar", "get_history_stats",
    "save_molecule", "rescoring_health", "rescoring_info", "rescoring_ram",
    "create_docking_proposal", "reconcile_operation",
}


def test_catalog_matches_declared_set():
    assert set(catalog()) == EXPECTED


def test_every_capability_declares_risk_class_and_provenance():
    for name, cap in catalog().items():
        assert cap.risk in ("read", "write", "approval_required"), name
        assert isinstance(cap.epistemic_class, EpistemicClass), name
        assert cap.provenance.startswith("MolDesign "), name
        entry = cap.as_catalog_entry()
        assert entry["epistemic_class"] == cap.epistemic_class.value
        assert entry["version"] == cap.version


def test_register_refuses_missing_provenance():
    with pytest.raises(ValueError, match="procedencia"):
        register(Capability("x", "d", "GET", "/x", {}, {}))


def test_unknown_capability_rejected():
    with pytest.raises(PlanValidationError):
        capability("execute_shell")


def test_request_splits_query_body_and_path():
    method, path, query, body, response = capability("save_molecule").request(
        {"molecule_id": "12345678-1234-1234-1234-123456789012",
         "name": "demo", "task_id": "t1"})
    assert method == "POST"
    assert path == "/history/save/12345678-1234-1234-1234-123456789012"
    assert query == {"name": "demo", "task_id": "t1"}
    assert body is None
    assert response == "json"


def test_post_body_stays_json_for_cancel():
    method, path, query, body, _ = capability("cancel_evaluation").request(
        {"task_id": "task-1"})
    assert (method, path, query, body) == (
        "POST", "/evaluation/cancel", {}, {"task_id": "task-1"})


def test_format_variants_select_paths():
    _, path, _, _, response = capability("export_batch").request(
        {"batch_id": "b1", "format": "csv"})
    assert path == "/evaluation/batch/b1/csv"
    assert response == "bytes"
    _, path, _, _, _ = capability("export_batch").request(
        {"batch_id": "b1", "format": "export"})
    assert path == "/evaluation/batch/b1/export"
    with pytest.raises(PlanValidationError):
        capability("export_batch").request({"batch_id": "b1", "format": "xml"})


def test_dossier_builds_minimal_projection():
    method, path, query, body, response = capability("get_case_dossier").request(
        {"molecule_id": "12345678-1234-1234-1234-123456789012",
         "format": "package", "task_id": "task-9"})
    assert path == "/dossier/12345678-1234-1234-1234-123456789012/package"
    assert query == {}
    assert body["run"] == {"task_id": "task-9"}
    assert body["case_id"].startswith("molchat-")
    assert response == "bytes"
    _, _, _, body2, _ = capability("get_case_dossier").request(
        {"molecule_id": "12345678-1234-1234-1234-123456789012",
         "format": "preview"})
    assert "run" not in body2  # latest result, no run claimed


def test_uuid_fields_reject_garbage():
    with pytest.raises(PlanValidationError):
        capability("get_evaluation_result").request({"molecule_id": "no-uuid"})
    method, path, _, _, _ = capability("get_evaluation_result").request(
        {"molecule_id": "12345678-1234-1234-1234-123456789012",
         "task_id": "task-3"})
    assert path == "/evaluation/result/12345678-1234-1234-1234-123456789012"


def test_binding_capable_capabilities_declare_outputs():
    assert "task_id" in capability("approve_docking_proposal").outputs
    assert "hash" in capability("get_docking_proposal").outputs
    assert "status" in capability("evaluation_status").outputs
    assert "items" in capability("list_evaluations").outputs
    assert "events" in capability("stream_evaluation").outputs


def test_field_locations_default_by_method():
    get_cap = Capability("g", "d", "GET", "/g", {}, {"a": FieldSpec(str)})
    _, _, query, body, _ = get_cap.request({"a": "x"})
    assert (query, body) == ({"a": "x"}, None)
    post_cap = Capability("p", "d", "POST", "/p", {}, {"a": FieldSpec(str)})
    _, _, query, body, _ = post_cap.request({"a": "x"})
    assert (query, body) == ({}, {"a": "x"})
