"""Meta Muse Spark planner. Produces proposals, never executes tools."""

from __future__ import annotations

import json

import httpx

from .capabilities import CAPABILITIES, PlanValidationError
from .config import load_config
from .plan import MAX_STEPS, Plan


_META_URL = "https://api.meta.ai/v1/chat/completions"


class MetaPlanner:
    def __init__(self, *, api_key: str | None = None, model: str = "muse-spark-1.3",
                 client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key or load_config().model_api_key
        if not self._key:
            raise ValueError("Falta MODEL_API_KEY; no se enviará el objetivo a Meta")
        self.model = model
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=60.0, trust_env=False)

    async def __aenter__(self) -> "MetaPlanner":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def plan(self, goal: str) -> Plan:
        if not isinstance(goal, str) or not 0 < len(goal) <= 4000:
            raise PlanValidationError("Objetivo no válido")
        # Approval-requiring actions are never selected autonomously by the LLM.
        safe_tools = [c.as_catalog_entry() for c in CAPABILITIES.values() if c.risk == "read"]
        schema = {
            "type": "object", "additionalProperties": False, "required": ["steps"],
            "properties": {"steps": {"type": "array", "minItems": 1,
                "maxItems": MAX_STEPS, "items": {"type": "object",
                    "additionalProperties": False,
                    "required": ["capability", "arguments", "rationale"],
                    "properties": {
                        "capability": {"type": "string", "enum": [t["name"] for t in safe_tools]},
                        "arguments": {"type": "object"},
                        "rationale": {"type": "string"},
                    },
                },
            }},
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": (
                    "Eres un planificador de química computacional. Propón SOLO una secuencia "
                    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
                    "datos de receptores ni resultados. Si faltan datos, usa solamente "
                    "list_targets u otra consulta válida. No realices diagnóstico clínico. "
                    "No hay ejecución en esta llamada. El protocolo científico lo decide MolDesign. "
                    "Devuelve el plan como JSON con la estructura indicada."
                )},
                {"role": "user", "content": json.dumps({"goal": goal, "capabilities": safe_tools},
                                                      ensure_ascii=False)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "molchat_readonly_plan", "strict": False, "schema": schema,
            }},
        }
        try:
            response = await self._client.post(
                _META_URL, json=payload,
                headers={"Authorization": f"Bearer {self._key}",
                         "Content-Type": "application/json"},
            )
            if response.status_code >= 400 or response.is_redirect:
                raise RuntimeError(f"Meta Model API devolvió HTTP {response.status_code}")
            content = response.json()["choices"][0]["message"]["content"]
            decoded = json.loads(content)
            steps = [dict(id=f"s{n}", **item) for n, item in enumerate(decoded["steps"], 1)]
            return Plan.from_dict({"goal": goal, "steps": steps, "planner": f"meta:{self.model}"})
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Meta no entregó un plan válido; no se ejecutó nada") from exc

