"""Adapter conformance kit (PLAN Fase 6, task 6.2; checks from §6.4).

Any adapter passes the same kit: the MolDesign adapter (here, against a
real MolDesign) today, third-party adapters (Fase 7, ``docs/ADAPTADORES.md``)
tomorrow. The five checks:

1. the declared catalog is sound and matches the served surface (no ghosts);
2. every capability rejects extra parameters and wrong types;
3. no ``read`` capability mutates state (recording backend + live oracle);
4. every non-``read`` capability without approval answers ``awaiting_approval``
   and sends nothing (the implemented rule is stronger than §6.4's wording,
   which names only ``approval_required``);
5. backend errors propagate as abstention (``failed``/``blocked`` with an
   error and no result), never as a fabricated number.

Checks 1b, 3b and 5b are the live legs (``--live``): without a reachable
backend or token they SKIP honestly, like the contract suite. Cases are
data (``cases/<pack>.json``): capabilities with validating arguments, live
flags, and auditable ``pending_surface`` notes for contracted-but-unreleased
routes. Third parties add their pack module (``--register``) and their cases
file; the runner imports nothing MolDesign-specific beyond the default packs.

Note (plan discrepancy): §5.1 places ``tools/reference.py`` in Fase 6 while
§17 defers it to 7.1. The kit stays portable without it: its offline doubles
plus a miniature foreign pack in the test-suite prove no MolDesign hardcoding.
The real reference backend remains a 7.1 deliverable.
"""

from .runner import main

__all__ = ["main"]
