"""Build the fixed Modal Sandbox bootstrap command."""
from __future__ import annotations

PREFLIGHT_EXIT_CODE_BASE = 64
PREFLIGHT_FAILURE_LINES = (43, 47, 56, 58, 62, 69, 72, 76)


def preflight_exit_code_map() -> dict[int, str]:
    """Map only registered workload preflight returns to stable diagnostics."""
    return {
        PREFLIGHT_EXIT_CODE_BASE + line: f"PREFLIGHT_RETURN_LINE_{line}"
        for line in PREFLIGHT_FAILURE_LINES
    }


def diagnostic_code_for_exit(exit_code: int | None) -> str | None:
    """Return a diagnostic only for exit codes emitted by the fixed bootstrap."""
    if type(exit_code) is not int:
        return None
    return preflight_exit_code_map().get(exit_code)


def normalize_exit_code(exit_code: int | None) -> tuple[int | None, str | None]:
    """Preserve existing exit-2 semantics while adding a bounded reason code."""
    diagnostic_code = diagnostic_code_for_exit(exit_code)
    return (2, diagnostic_code) if diagnostic_code else (exit_code, None)


def sandbox_entrypoint(
    inference_path: str = "/work/inference.py",
    *,
    drop_privileges: bool = True,
) -> tuple[str, str, str, str]:
    """Run only the pinned inference file and preserve its bounded exit signal."""
    code = ["import os,sys"]
    if drop_privileges:
        code.extend(("os.setgroups([])", "os.setgid(10001)", "os.setuid(10001)"))
    code.extend((
        "failure_line=[None]",
        "allowed_failure_lines=" + repr(PREFLIGHT_FAILURE_LINES),
        "def trace(frame,event,arg):",
        "    if frame.f_code.co_filename != " + repr(inference_path) + ":",
        "        return None",
        "    if event=='return' and frame.f_code.co_name=='main' and type(arg) is int and arg==2:",
        "        failure_line[0]=frame.f_lineno",
        "        sys.stderr.write('GPU_CONTROL_PREFLIGHT_RETURN_LINE='+str(frame.f_lineno)+'\\n')",
        "    return trace",
        "sys.settrace(trace)",
        "try:",
        "    __import__('runpy').run_path(" + repr(inference_path) + ",run_name='__main__')",
        "except SystemExit as error:",
        "    if type(error.code) is int and error.code==2 and failure_line[0] in allowed_failure_lines:",
        "        raise SystemExit(" + str(PREFLIGHT_EXIT_CODE_BASE) + " + failure_line[0])",
        "    if type(error.code) is int and error.code != 0:",
        "        os.write(2, ('GPU_CONTROL_SANDBOX_SYSTEM_EXIT=' + str(error.code) + '\\n').encode('ascii'))",
        "    raise",
    ))
    return ("python", "-I", "-c", "\n".join(code))
