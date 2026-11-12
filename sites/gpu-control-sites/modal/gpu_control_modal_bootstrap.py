"""Build the fixed Modal Sandbox bootstrap command."""
from __future__ import annotations


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
        "trace=lambda frame,event,arg: ((sys.stderr.write('GPU_CONTROL_PREFLIGHT_RETURN_LINE='+str(frame.f_lineno)+'\\n') "
        "if event=='return' and frame.f_code.co_filename==" + repr(inference_path) + " and frame.f_code.co_name=='main' "
        "and type(arg) is int and arg==2 else None) or trace) "
        "if frame.f_code.co_filename==" + repr(inference_path) + " else None",
        "sys.settrace(trace)",
        "try:",
        "    __import__('runpy').run_path(" + repr(inference_path) + ",run_name='__main__')",
        "except SystemExit as error:",
        "    if type(error.code) is int and error.code != 0:",
        "        os.write(2, ('GPU_CONTROL_SANDBOX_SYSTEM_EXIT=' + str(error.code) + '\\n').encode('ascii'))",
        "    raise",
    ))
    return ("python", "-I", "-c", "\n".join(code))
