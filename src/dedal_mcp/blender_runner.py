"""Run Blender in headless mode to execute bpy scripts."""

import os
import subprocess
import tempfile


BLENDER_PATH = os.environ.get("BLENDER_PATH", "blender")


class BlenderError(Exception):
    pass


def run_script(script: str, timeout: int = 60) -> str:
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
