"""Specialist-agent collaboration layer for VendorVerdict.

The public ASI:One uAgent stays in ``vendorverdict.agent``.  This package
contains deterministic specialist worker agents that the orchestrator calls to
complete the vendor-risk workflow.  The separation keeps the demo reliable while
making the multi-agent responsibilities explicit and testable.
"""

from .multiagent import VendorVerdictMultiAgentOrchestrator

__all__ = ["VendorVerdictMultiAgentOrchestrator"]
