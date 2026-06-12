"""Run Blender in headless mode to execute bpy scripts."""

from __future__ import annotations

import os
import subprocess
import tempfile


BLENDER_PATH = os.environ.get("BLENDER_PATH", "blender")

# Cold Blender starts (first launch, addon caches) can exceed 60s on slow
# machines — overridable without code changes.
DEFAULT_TIMEOUT = int(os.environ.get("DEDAL_BLENDER_TIMEOUT", "120"))


class BlenderError(Exception):
    pass


def run_script(script: str, timeout: int | None = None) -> str:
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, prefix="dedal_"
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [BLENDER_PATH, "--background", "--python", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        stdout = result.stdout
        stderr = result.stderr

        if result.returncode != 0:
            error_lines = [
                l for l in stderr.split("\n")
                if l.strip() and not l.startswith("Info:")
            ]
            raise BlenderError(
                f"Blender exited with code {result.returncode}.\n"
                + "\n".join(error_lines[-10:])
            )

        successes = [
            l.split("DEDAL_EXPORT_SUCCESS:")[1]
            for l in stdout.split("\n")
            if "DEDAL_EXPORT_SUCCESS:" in l
        ]

        errors = [
            l.split("DEDAL_ERROR:")[1].strip()
            for l in stdout.split("\n")
            if "DEDAL_ERROR:" in l
        ]

        return _format_result(successes, errors)

    except subprocess.TimeoutExpired:
        raise BlenderError(f"Blender timed out after {timeout}s")
    except FileNotFoundError:
        raise BlenderError(
            f"Blender not found at '{BLENDER_PATH}'. "
            f"Set the BLENDER_PATH environment variable to the Blender executable path."
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _format_result(successes: list[str], errors: list[str]) -> str:
    parts = []
    if successes:
        parts.append(f"Exported {len(successes)} file(s):")
        for path in successes:
            size = ""
            try:
                size = f" ({os.path.getsize(path.strip())} bytes)"
            except OSError:
                pass
            parts.append(f"  {path.strip()}{size}")
    if errors:
        parts.append(f"Errors ({len(errors)}):")
        for e in errors:
            parts.append(f"  {e}")
    if not parts:
        parts.append("Script completed (no export markers found)")
    return "\n".join(parts)


def run_render(
    script: str,
    scene_path: str | None = None,
    timeout: int = 600,
) -> tuple[list[str], list[str], list[str]]:
    """Run Blender headless to render. If *scene_path* is given, Blender opens
    that .blend first; otherwise renders against the default empty scene.

    Returns:
        (rendered_paths, warnings, errors)

    Parses stdout for ``DEDAL_RENDER_SUCCESS:<path>`` and
    ``DEDAL_RENDER_WARNING:<msg>`` markers. Raises BlenderError on subprocess
    failure or timeout.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, prefix="dedal_render_"
    ) as f:
        f.write(script)
        script_path = f.name

    cmd = [BLENDER_PATH, "--background"]
    if scene_path:
        cmd.append(scene_path)
    cmd.extend(["--python", script_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout = result.stdout
        stderr = result.stderr

        if result.returncode != 0:
            error_lines = [
                l for l in stderr.split("\n")
                if l.strip() and not l.startswith("Info:")
            ]
            raise BlenderError(
                f"Blender exited with code {result.returncode}.\n"
                + "\n".join(error_lines[-15:])
            )

        rendered = [
            l.split("DEDAL_RENDER_SUCCESS:", 1)[1].strip()
            for l in stdout.split("\n")
            if "DEDAL_RENDER_SUCCESS:" in l
        ]
        warnings = [
            l.split("DEDAL_RENDER_WARNING:", 1)[1].strip()
            for l in stdout.split("\n")
            if "DEDAL_RENDER_WARNING:" in l
        ]
        errors = [
            l.split("DEDAL_ERROR:", 1)[1].strip()
            for l in stdout.split("\n")
            if "DEDAL_ERROR:" in l
        ]
        return rendered, warnings, errors

    except subprocess.TimeoutExpired:
        raise BlenderError(f"Blender render timed out after {timeout}s")
    except FileNotFoundError:
        raise BlenderError(
            f"Blender not found at '{BLENDER_PATH}'. "
            f"Set the BLENDER_PATH environment variable."
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
