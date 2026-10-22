"""Deterministic, CPU-only checks before any model call."""

from gatekeeper.gates.senior_role_gate import GateDecision, senior_role_gate

__all__ = ["GateDecision", "senior_role_gate"]
