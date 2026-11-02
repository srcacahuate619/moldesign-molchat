"""Save in Moldex and ask Molcy for a video: the tools prepare, only the confirmed run writes."""
import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation import product_actions as pa

from tests.conversation.fake_moldesign import MOLECULE, TASK, VIDEO_JOB, FakeMolDesign

TOKEN = "test-account-token"


def bridge_for(fake: FakeMolDesign | None = None, handler=None):
    fake = fake or FakeMolDesign()
    client = httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler or fake.handler))
    return MolDesignBridge(client=client, token=TOKEN), client, fake


def proposer(sink):
    def propose(kind, spec, summary):
        sink.append((kind, spec, summary))
        return {"id": f"p{len(sink)}"}
    return propose


VIDEO = {"task_id": TASK, "scene": "resultado", "format": "horizontal"}


# ── The recipe is Molcy's own; what the person did not ask for does not travel ─────────────────────

def test_only_what_was_asked_becomes_part_of_the_recipe():
    recipe, problem = pa.build_presentation({"title": "  VMAT2 y la tetrabenazina ", "color_receptor": "#aabbcc",
                                             "color_polar": "#112233", "receptor": "oculto", "labels": "no"})
    assert problem is None
    assert recipe == {"titulo": "VMAT2 y la tetrabenazina", "color_receptor": "#AABBCC",
                      "colores_lineas": {"polar": "#112233"}, "receptor": "oculto", "etiquetas": False}
    assert pa.build_presentation({}) == ({}, None)


@pytest.mark.parametrize("args", [
    {"title": "   "}, {"title": "x" * 81}, {"title": "con\x00control"}, {"title": "con\u202ebidi"},
    {"color_receptor": "rojo"}, {"color_residuos": "#12345"}, {"color_polar": "#GGGGGG"}, {"color_apolar": "#1234567"},
    {"receptor": "transparente"}, {"labels": "tal vez"}, {"contacts": "true"}, {"show_previous": "1"}])
def test_a_recipe_molcy_would_reject_is_not_proposed(args):
    recipe, problem = pa.build_presentation(args)
    assert recipe is None and problem


# ── Claims of a done deed are corrected; nearby wording is left alone (negative controls) ──────────

@pytest.mark.parametrize("claim", [
    "Se guardó la corrida en Moldex.", "Ya he guardado el resultado.", "Guardé la evaluación.", "Quedó guardada en Moldex.",
    "Generé el vídeo con tu título.", "Se inició el vídeo de la escena resultado.", "He enviado el video a Molcy."])
def test_a_claim_that_something_was_done_is_corrected(claim):
    corrected = pa.mask_unconfirmed_actions(claim)
    assert "No se confirmó" in corrected and corrected != claim


@pytest.mark.parametrize("fine", [
    "Esta corrida ya está guardada en Moldex.", "Quieres que guarde la corrida?", "No se guardó nada.",
    "Sin guardar no puedo hacer el vídeo.", "El vídeo se genera con tu GPU y puede tardar.", "Para generar el vídeo hace falta una GPU.",
    "No se generó ningún vídeo."])
def test_wording_that_does_not_claim_an_action_is_not_rewritten(fine):
    assert pa.mask_unconfirmed_actions(fine) == fine


# ── Preparing writes nothing ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_saving_is_prepared_with_the_run_as_moldesign_reports_it_and_nothing_is_written():
    bridge, client, fake = bridge_for()
    sink = []
    async with client:
        result = await pa.save_to_moldex_tool(bridge, proposer(sink)).execute({"task_id": TASK, "name": " Mi corrida "})
    assert result["status"] == "awaiting_confirmation" and result["action_id"] == "p1"
    (kind, spec, summary), = sink
    assert kind == pa.SAVE and spec == {"molecule_id": MOLECULE, "task_id": TASK, "name": "Mi corrida"}
    assert "Corrida t-8t69 · receptor VMAT2" in summary["lines"][0] and "Nombre: Mi corrida" in summary["lines"]
    assert fake.writes() == []
    assert {call.auth for call in fake.calls} == {f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_a_run_that_is_already_in_moldex_is_not_proposed_again():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=True))
    sink = []
    async with client:
        result = await pa.save_to_moldex_tool(bridge, proposer(sink)).execute({"task_id": TASK})
    assert result["status"] == "already_saved" and sink == [] and fake.writes() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,args", [("save", {"task_id": TASK}), ("video", VIDEO)])
async def test_a_run_that_did_not_finish_cannot_be_saved_or_filmed(tool_name, args):
    bridge, client, fake = bridge_for(FakeMolDesign(job_status="STARTED"))
    sink = []
    make = pa.save_to_moldex_tool if tool_name == "save" else pa.molcy_video_tool
    async with client:
        result = await make(bridge, proposer(sink)).execute(args)
    assert result["status"] == "not_ready" and result["task_status"] == "STARTED" and sink == [] and fake.writes() == []


@pytest.mark.asyncio
async def test_a_video_of_a_saved_run_is_prepared_with_its_recipe_and_the_closing_is_declared():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=True))
    sink = []
    async with client:
        result = await pa.molcy_video_tool(bridge, proposer(sink)).execute(
            {**VIDEO, "title": "Mi vídeo", "receptor": "oculto", "color_polar": "#00ff00"})
    assert result["status"] == "awaiting_confirmation"
    (kind, spec, summary), = sink
    assert kind == pa.VIDEO and spec["save_first"] is False
    assert spec["presentation"] == {"titulo": "Mi vídeo", "receptor": "oculto", "colores_lineas": {"polar": "#00FF00"}}
    text = "\n".join(summary["lines"])
    assert "Escena: resultado · Formato: horizontal (biblioteca)" in text and "Título: Mi vídeo" in text
    assert "cierre de MolDesign se añade siempre" in text and "Se guardará primero" not in text
    assert fake.writes() == []


@pytest.mark.asyncio
async def test_a_video_of_an_unsaved_run_says_it_will_be_saved_first():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=False))
    sink = []
    async with client:
        result = await pa.molcy_video_tool(bridge, proposer(sink)).execute(VIDEO)
    assert result["status"] == "awaiting_confirmation"
    (_, spec, summary), = sink
    assert spec["save_first"] is True and summary["saves_first"] is True
    assert any("Se guardará primero en Moldex" in line for line in summary["lines"]) and fake.writes() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fake,status", [
    (FakeMolDesign(saved=True, renderer_available=False), "renderer_unavailable"),
    (FakeMolDesign(saved=True, gpu=False), "renderer_unavailable"),
    (FakeMolDesign(saved=True, source_available=False), "source_unavailable"),
    (FakeMolDesign(saved=True, scenes=("receptor",)), "scene_unavailable"),
])
async def test_when_the_machine_or_the_run_cannot_make_the_video_there_is_no_proposal(fake, status):
    bridge, client, fake = bridge_for(fake)
    sink = []
    async with client:
        result = await pa.molcy_video_tool(bridge, proposer(sink)).execute(VIDEO)
    assert result["status"] == status and sink == [] and fake.writes() == []
    assert result["message"]


@pytest.mark.asyncio
async def test_no_gpu_is_reported_with_the_reason_molcy_gives_and_nothing_is_installed():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=True, gpu=False))
    async with client:
        result = await pa.molcy_video_tool(bridge, proposer([])).execute(VIDEO)
    assert "GPU" in result["message"] and all(call.method == "GET" for call in fake.calls)


@pytest.mark.asyncio
async def test_the_scenes_a_run_does_offer_are_named_when_the_asked_one_is_not_available():
    bridge, client, _ = bridge_for(FakeMolDesign(saved=True, scenes=("receptor",)))
    async with client:
        result = await pa.molcy_video_tool(bridge, proposer([])).execute(VIDEO)
    assert result["available_scenes"] == ["receptor"]


@pytest.mark.asyncio
async def test_an_invalid_recipe_stops_before_anything_is_asked_of_moldesign():
    bridge, client, fake = bridge_for()
    async with client:
        result = await pa.molcy_video_tool(bridge, proposer([])).execute({**VIDEO, "color_polar": "verde"})
    assert result["status"] == "invalid" and fake.calls == []


@pytest.mark.asyncio
async def test_without_the_accounts_session_nothing_is_asked():
    client = httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(FakeMolDesign().handler))
    async with client:
        result = await pa.save_to_moldex_tool(MolDesignBridge(client=client), proposer([])).execute({"task_id": TASK})
    assert result["status"] == "unavailable"


# ── Running: only after the click, with the exact body Molcy validates ─────────────────────────────

def spec_for(**extra):
    return {"molecule_id": MOLECULE, "task_id": TASK, "scene": "resultado", "format": "vertical",
            "presentation": {"titulo": "Mi vídeo"}, "save_first": False, **extra}


@pytest.mark.asyncio
async def test_a_confirmed_save_posts_to_moldex_for_that_run_only():
    bridge, client, fake = bridge_for()
    async with client:
        outcome = await pa.run_save(bridge, {"molecule_id": MOLECULE, "task_id": TASK, "name": "Mi corrida"})
    assert outcome["status"] == "saved" and outcome["name"] == "Mi corrida"
    (call,) = fake.writes()
    assert (call.method, call.path, call.params, call.auth) == ("POST", f"/history/save/{MOLECULE}",
                                                                {"task_id": TASK, "name": "Mi corrida"}, f"Bearer {TOKEN}")


@pytest.mark.asyncio
async def test_a_confirmed_video_posts_the_exact_job_molcy_validates():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=True))
    async with client:
        outcome = await pa.run_video(bridge, spec_for())
    assert outcome["status"] == "started" and outcome["job_id"] == VIDEO_JOB and outcome["saved_first"] is False
    (call,) = fake.writes()
    assert call.path == "/molcy/trabajos" and call.body == {
        "origen": "moldex", "id": MOLECULE, "task_id": TASK, "escena": "resultado", "formato": "vertical",
        "dispositivo": "gpu", "presentacion": {"titulo": "Mi vídeo"}}
    assert "cpu_hilos" not in call.body and "ensamble_fluido" not in call.body


@pytest.mark.asyncio
async def test_a_video_of_an_unsaved_run_saves_it_first_and_in_that_order():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=False))
    async with client:
        outcome = await pa.run_video(bridge, spec_for(save_first=True))
    assert outcome["status"] == "started" and outcome["saved_first"] is True
    assert [(call.method, call.path) for call in fake.writes()] == [("POST", f"/history/save/{MOLECULE}"), ("POST", "/molcy/trabajos")]


@pytest.mark.asyncio
async def test_if_the_save_fails_the_video_is_not_asked_for():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=False, save_status=409))
    async with client:
        outcome = await pa.run_video(bridge, spec_for(save_first=True))
    assert outcome["status"] == "rejected" and "no se pidió el vídeo" in outcome["message"]
    assert [call.path for call in fake.writes()] == [f"/history/save/{MOLECULE}"]


@pytest.mark.asyncio
async def test_a_scene_that_stopped_being_available_between_proposal_and_click_is_not_sent():
    bridge, client, fake = bridge_for(FakeMolDesign(saved=True, scenes=("receptor",)))
    async with client:
        outcome = await pa.run_video(bridge, spec_for())
    assert outcome["status"] == "scene_unavailable" and fake.writes() == []


@pytest.mark.asyncio
async def test_molcy_refusal_is_reported_with_its_reason_and_not_as_started():
    bridge, client, _ = bridge_for(FakeMolDesign(saved=True, video_status=409, video_reply={"detail": "No hay una GPU compatible."}))
    async with client:
        outcome = await pa.run_video(bridge, spec_for())
    assert outcome["status"] == "rejected" and "No hay una GPU compatible." in outcome["message"] and "job_id" not in outcome


@pytest.mark.asyncio
async def test_a_validation_error_from_molcy_names_the_field():
    reply = {"detail": [{"loc": ["body", "presentacion", "titulo"], "msg": "String should have at most 80 characters"}]}
    bridge, client, _ = bridge_for(FakeMolDesign(saved=True, video_status=422, video_reply=reply))
    async with client:
        outcome = await pa.run_video(bridge, spec_for())
    assert outcome["status"] == "rejected" and "presentacion.titulo" in outcome["message"]


@pytest.mark.asyncio
async def test_a_lost_answer_to_the_video_request_is_unknown_never_nothing_happened():
    fake = FakeMolDesign(saved=True)
    def handler(request):
        if request.method == "POST":
            raise httpx.ReadTimeout("sin respuesta", request=request)
        return fake.handler(request)
    bridge, client, _ = bridge_for(fake, handler)
    async with client:
        outcome = await pa.run_video(bridge, spec_for())
    assert outcome["status"] == "unknown" and "Molcy" in outcome["message"] and "no se pidió nada" not in outcome["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("code,status", [(401, "session_expired"), (403, "session_expired"), (404, "not_found"), (500, "failed")])
async def test_save_errors_become_a_plain_status(code, status):
    bridge, client, _ = bridge_for(FakeMolDesign(save_status=code))
    async with client:
        outcome = await pa.run_save(bridge, {"molecule_id": MOLECULE, "task_id": TASK, "name": None})
    assert outcome["status"] == status


@pytest.mark.asyncio
async def test_an_id_from_moldesign_that_is_not_an_id_is_not_trusted():
    bridge, client, _ = bridge_for(FakeMolDesign(saved=True, video_reply={"id": "../../etc", "estado": "en_cola"}))
    async with client:
        outcome = await pa.run_video(bridge, spec_for())
    assert outcome["status"] == "unknown" and "job_id" not in outcome


# ── Following a video ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_status_of_a_video_is_read_only_and_keeps_to_known_fields():
    reply = {"id": VIDEO_JOB, "estado": "renderizando", "formato": "biblioteca", "fase": "Renderizando",
             "progreso": {"fotogramas": 120, "total": 480, "ruta_privada": "cuenta-privada/videos"}, "restante_render_principal_s": 95,
             "carpeta": "cuenta-privada/molcy/videos"}
    bridge, client, fake = bridge_for(FakeMolDesign(state_reply=reply))
    async with client:
        result = await pa.molcy_video_status_tool(bridge).execute({"job_id": VIDEO_JOB})
    assert result == {"status": "ok", "job_id": VIDEO_JOB, "job_state": "renderizando", "source": "MolDesign GET /molcy/trabajos",
                      "format": "biblioteca", "phase": "Renderizando", "progress": {"frames": 120, "total": 480}, "remaining_seconds": 95}
    assert fake.writes() == [] and "cuenta-privada" not in str(result)


@pytest.mark.asyncio
async def test_a_finished_video_points_to_the_molcy_tab_and_a_foreign_one_is_not_found():
    bridge, client, _ = bridge_for(FakeMolDesign(state_reply={"id": VIDEO_JOB, "estado": "completo"}))
    async with client:
        done = await pa.molcy_video_status_tool(bridge).execute({"job_id": VIDEO_JOB})
        other = await pa.molcy_video_status_tool(bridge).execute({"job_id": "99999999-2222-4333-8444-555555555555"})
        bad = await pa.molcy_video_status_tool(bridge).execute({"job_id": "../etc/passwd"})
    assert done["job_state"] == "completo" and "pestaña Molcy" in done["note"]
    assert other["status"] == "not_found" and bad["status"] == "invalid"


def test_the_tools_ask_for_what_the_person_must_decide_and_nothing_else():
    required = pa.molcy_video_tool(bridge_for()[0], proposer([])).parameters["required"]
    assert set(required) == {"task_id", "scene", "format"}
    properties = pa.molcy_video_tool(bridge_for()[0], proposer([])).parameters["properties"]
    assert not {"cierre", "closing", "dispositivo", "device", "motor", "engine", "salida", "cpu"} & set(properties)
