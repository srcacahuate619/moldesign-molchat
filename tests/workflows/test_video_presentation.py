"""Molcy's whole presentation, asked from the chat: «hotspots en verde y el receptor morado» must reach the card the person
approves and Molcy's own schema, and anything that is not a real control or a real colour is refused before approval."""
from __future__ import annotations

import json
from typing import Any

import pytest

from molchat_agent.conversation.tool_loop import _arguments
from molchat_agent.workflows.iteration import IterationSpec, SpecError, VideoRequest
from molchat_agent.workflows.tool import propose_iteration_tool

BASE = {"case_name": "Iteración VMAT2", "pdb_id": "8T69", "threshold_kcal": -9.0,
        "molecules": [{"name": "tetrabenazina", "smiles": "CC(C)CC1CN2CCC3=CC(=C(C=C3C2CC1=O)OC)OC"}]}
CUSTOM = {"scene": "busqueda", "format": "previsualizacion", "residue_color": "#22c55e", "receptor_color": "#8B5CF6",
          "labels": False, "title": "Tetrabenazina en VMAT2"}


def test_the_presentation_reaches_molcys_schema_and_the_card() -> None:
    spec = IterationSpec.from_dict({**BASE, "video": CUSTOM})
    video = spec.video
    assert video is not None
    assert video.presentation() == {
        "schema": "moldesign.presentacion/1", "titulo": "Tetrabenazina en VMAT2", "color_receptor": "#8B5CF6",
        "color_residuos": "#22C55E", "colores_lineas": {"polar": None, "apolar": None}, "receptor": "automatico",
        "muestra_anterior": True, "etiquetas": False, "contactos": True}
    lines = "\n".join(spec.card_lines())
    assert "formato prueba (vista previa corta)" in lines
    assert "color de los residuos destacados #22C55E" in lines and "color del receptor #8B5CF6" in lines
    assert "sin etiquetas" in lines and "título «Tetrabenazina en VMAT2»" in lines


def test_an_untouched_video_says_it_uses_molcys_automatic_presentation_and_a_change_changes_the_digest() -> None:
    plain = IterationSpec.from_dict({**BASE, "video": {"scene": "busqueda"}})
    assert plain.video is not None and plain.video.format == "horizontal" and plain.video.customized() == []
    assert "Presentación: la automática de Molcy." in plain.card_lines()
    custom = IterationSpec.from_dict({**BASE, "video": {"scene": "busqueda", "residue_color": "#22C55E"}})
    assert plain.digest != custom.digest  # the approval is bound to the colours too


@pytest.mark.parametrize("video", [
    {"scene": "busqueda", "residue_color": "verde"}, {"scene": "busqueda", "receptor_color": "#12345"},
    {"scene": "busqueda", "receptor": "transparente"}, {"scene": "busqueda", "labels": "no"},
    {"scene": "busqueda", "brillo": 3}, {"scene": "ensamble", "ensemble_variant": "rapida"},
])
def test_what_is_not_a_molcy_control_or_a_colour_is_refused(video: dict[str, Any]) -> None:
    with pytest.raises(SpecError):
        IterationSpec.from_dict({**BASE, "video": video})


def test_previous_sample_only_matters_in_the_search_scene_and_the_variant_only_in_the_ensemble() -> None:
    result = VideoRequest.from_dict({"scene": "resultado", "previous_sample": False, "ensemble_variant": "detallada"})
    assert result.customized() == []
    ensemble = VideoRequest.from_dict({"scene": "ensamble", "ensemble_variant": "detallada"})
    assert ensemble.customized() == ["movimiento del ensamble: detallada"]


async def test_the_model_tool_takes_the_colours_and_leaves_a_card_and_refuses_a_name_instead_of_a_code() -> None:
    proposed: list[IterationSpec] = []
    tool = propose_iteration_tool("hazlo con los hotspots en verde y el receptor morado",
                                  lambda spec: proposed.append(spec) or {"id": "w1", "lines": spec.card_lines()})
    args = _arguments(json.dumps({**BASE, "video": {"scene": "busqueda", "residue_color": "#22C55E", "receptor_color": "#8B5CF6"}}),
                      tool.parameters)
    answer = await tool.execute(args)
    assert answer["status"] == "awaiting_approval" and proposed[0].video is not None
    assert proposed[0].video.residue_color == "#22C55E" and proposed[0].video.receptor_color == "#8B5CF6"
    try:
        bad = _arguments(json.dumps({**BASE, "video": {"scene": "busqueda", "residue_color": "verde"}}), tool.parameters)
    except ValueError:
        return  # refused by the closed schema
    assert (await tool.execute(bad))["status"] == "invalid"  # or by the plan itself, before any card


async def test_the_model_tool_preserves_requested_time_limits_in_the_approved_spec() -> None:
    proposed: list[IterationSpec] = []
    tool = propose_iteration_tool("60 seconds per molecule and 180 seconds total",
        lambda spec: proposed.append(spec) or {"id": "w1", "lines": spec.card_lines()})
    args = _arguments(json.dumps({**BASE, "per_molecule_timeout_s": 60, "budget_s": 180}), tool.parameters)
    result = await tool.execute(args)
    assert result["status"] == "awaiting_approval"
    assert proposed[0].per_molecule_timeout_s == 60 and proposed[0].budget_s == 180
    assert proposed[0].digest != IterationSpec.from_dict(BASE).digest
    for invalid in ({"per_molecule_timeout_s": 29}, {"budget_s": 7201}, {"budget_s": True}):
        with pytest.raises(ValueError):
            _arguments(json.dumps({**BASE, **invalid}), tool.parameters)
