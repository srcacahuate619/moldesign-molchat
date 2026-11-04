# Automated reproduction of the real VMAT2 campaign

This second, independent browser campaign ran the public [`run_capsule.cjs`](../../run_capsule.cjs) script against the same isolated capsule. It created a new case and performed new Vina jobs and a new Molcy render; it did not replay the first run's outputs.

[Execution and assertions](execution.json) · [Original delivery](delivery.zip) · [Manifest](MANIFEST.json) · [Notebook](notebook.md)

The script checks the candidate order, zero dispatched mutations before approval, rejection of a wrong digest, completed video, two evaluated candidates plus one skipped, selected identity and physical checks, Moldex save, Preparation's preserved REVIEW, and absence of extra evaluations after a repeated approval.

The recorded outcome again stopped at ketanserin after aspirin did not reach the threshold. Both original deliveries are retained separately. This is a repeat under one machine/protocol, not a scientific replication across independent laboratories. [Capsule conditions and emulation limits](../capsule/conditions.json)
