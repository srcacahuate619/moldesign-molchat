"""MolDesign pack: one row per verified endpoint (no ghosts)."""

import pytest

from molchat_agent.tools import capability


@pytest.mark.parametrize("name,method,path,risk", [
    ("list_targets", "GET", "/targets/", "read"),
    ("check_preflight", "POST", "/evaluation/preflight", "read"),
    ("list_evaluations", "GET", "/history/evaluations", "read"),
    ("evaluation_status", "GET", "/evaluation/status/{task_id}", "read"),
    ("get_docking_proposal", "GET", "/ai/proposals/{proposal_id}", "read"),
    ("approve_docking_proposal", "POST", "/ai/proposals/{proposal_id}/approve",
     "approval_required"),
    ("list_engines", "GET", "/evaluation/engines", "read"),
    ("get_evaluation_result", "GET", "/evaluation/result/{molecule_id}", "read"),
    ("get_interactions", "GET", "/evaluation/interactions/{molecule_id}", "read"),
    ("get_gnn_attention", "GET", "/evaluation/gnn-attention/{molecule_id}", "read"),
    ("stream_evaluation", "GET", "/evaluation/stream/{task_id}", "read"),
    ("cancel_evaluation", "POST", "/evaluation/cancel", "write"),
    ("batch_status", "GET", "/evaluation/batch/{batch_id}", "read"),
    ("cancel_batch", "POST", "/evaluation/batch/{batch_id}/cancel", "write"),
    ("export_batch", "GET", "/evaluation/batch/{batch_id}/{format}", "read"),
    ("get_ai_report", "POST", "/evaluation/ai-report/{molecule_id}", "read"),
    ("stream_ai_report", "GET", "/evaluation/ai-report/{molecule_id}/stream", "read"),
    ("get_case_dossier", "POST", "/dossier/{molecule_id}/{format}", "read"),
    ("get_sar", "GET", "/sar/{molecule_id}", "read"),
    ("get_history_stats", "GET", "/history/stats", "read"),
    ("save_molecule", "POST", "/history/save/{molecule_id}", "write"),
    ("rescoring_health", "GET", "/rescoring/health", "read"),
    ("rescoring_info", "GET", "/rescoring/info", "read"),
    ("rescoring_ram", "GET", "/rescoring/ram", "read"),
])
def test_endpoint_contracts(name, method, path, risk):
    cap = capability(name)
    assert cap.method == method
    assert cap.path == path
    assert cap.risk == risk


@pytest.mark.parametrize("name", ["create_docking_proposal", "start_batch"])
def test_unavailable_capabilities_do_not_exist(name):
    """No endpoint (proposals) or no agent bytes (batch file): abstain by absence."""
    from molchat_agent.tools import PlanValidationError, catalog
    assert name not in catalog()
    with pytest.raises(PlanValidationError):
        capability(name)
