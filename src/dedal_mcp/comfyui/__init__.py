"""ComfyUI client + workflow input injection.

Submits a ComfyUI API-format workflow JSON to a running server, injects the
AI-provided inputs into nodes identified by their title (the user renames
target nodes to ``DEDAL_INPUT_*``, ``DEDAL_PROMPT``, ``DEDAL_SEED``,
``DEDAL_OUTPUT*``), polls until the prompt completes, and downloads the
resulting images to a local directory.
"""

from dedal_mcp.comfyui.workflow import (
    WorkflowError,
    load_workflow,
    inject_inputs,
    find_output_nodes,
    list_workflows,
)
from dedal_mcp.comfyui.client import (
    ComfyError,
    submit_prompt,
    poll_history,
    upload_image,
    fetch_output,
)

__all__ = [
    "WorkflowError", "load_workflow", "inject_inputs", "find_output_nodes", "list_workflows",
    "ComfyError", "submit_prompt", "poll_history", "upload_image", "fetch_output",
]
