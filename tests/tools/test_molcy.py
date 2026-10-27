"""Molcy pack: video jobs orchestrated (rendered by the platform)."""

import pytest

from molchat_agent.tools import PlanValidationError, capability


@pytest.mark.parametrize("name,method,path,risk", [
    ("molcy_fuentes", "GET", "/molcy/fuentes", "read"),
    ("request_case_video", "POST", "/molcy/trabajos", "write"),
    ("molcy_job_status", "GET", "/molcy/trabajos/{job_id}", "read"),
    ("get_video_acta", "GET", "/molcy/trabajos/{job_id}/procedencia", "read"),
    ("cancel_molcy_job", "POST", "/molcy/trabajos/{job_id}/cancelar", "write"),
])
def test_endpoint_contracts(name, method, path, risk):
    cap = capability(name)
    assert cap.method == method
    assert cap.path == path
    assert cap.risk == risk


def test_request_builds_nuevo_trabajo_body():
    method, path, query, body, response = capability("request_case_video").request({
        "origen": "moldex", "id": "12345678-1234-1234-1234-123456789012",
        "escena": "resultado", "formato": "horizontal", "task_id": "task-1"})
    assert method == "POST"
    assert path == "/molcy/trabajos"
    assert query == {}
    assert body == {"origen": "moldex", "id": "12345678-1234-1234-1234-123456789012",
                    "escena": "resultado", "formato": "horizontal",
                    "task_id": "task-1"}
    assert response == "json"


@pytest.mark.parametrize("args", [
    {"origen": "nube", "id": "1HSG", "escena": "resultado", "formato": "horizontal"},
    {"origen": "moldex", "id": "1HSG", "escena": "retrato", "formato": "horizontal"},
    {"origen": "moldex", "id": "1HSG", "escena": "resultado", "formato": "imax"},
    {"origen": "moldex", "id": "x", "escena": "resultado", "formato": "horizontal"},
])
def test_request_rejects_invalid_enums(args):
    with pytest.raises(PlanValidationError):
        capability("request_case_video").request(args)


def test_job_paths_need_uuids():
    with pytest.raises(PlanValidationError):
        capability("molcy_job_status").request({"job_id": "no-uuid"})
    _, path, _, _, _ = capability("get_video_acta").request(
        {"job_id": "12345678-1234-1234-1234-123456789012"})
    assert path == "/molcy/trabajos/12345678-1234-1234-1234-123456789012/procedencia"


def test_follow_outputs_declared():
    assert "estado" in capability("molcy_job_status").outputs
    assert "id" in capability("request_case_video").outputs
    assert "moldex" in capability("molcy_fuentes").outputs
