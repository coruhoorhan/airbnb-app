"""
Magda-Agent Backend & E2E Bridge for Veyyon & Codex.
"""

from magda_agent.backend_bridge.backend_cli import (
    load_backend_manifest,
    save_backend_manifest,
    render_subagent_prompt,
)

__all__ = ["load_backend_manifest", "save_backend_manifest", "render_subagent_prompt"]
