"""Fixed, network-isolated Modal T4 compute canary.

This function is intentionally not a generic execution surface.  It accepts
only owner-bound control-plane identifiers and launches one embedded CUDA
kernel.  No provider or control-plane secret is attached to the GPU container.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import re
from typing import Any

import modal


APP_NAME = "gpu-control-modal-gpu-canary"
WORKLOAD = "modal-gpu-vector-add-v1"
BASE_IMAGE_DIGEST = "sha256:c67e92c8099ba22853ab4cfda7cfb494d253d6012ca82dee98ba8976772af018"
RUN_ID = re.compile(r"^[0-9a-f]{32}$")
SOURCE_SHA = re.compile(r"^[0-9a-f]{40}$")
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")

# Four-thread vector addition.  PTX is embedded and reviewed; callers cannot
# provide code, arguments, images, URLs, environment variables, or commands.
PTX = rb"""
.version 7.0
.target sm_70
.address_size 64

.visible .entry vector_add(
    .param .u64 a,
    .param .u64 b,
    .param .u64 c
)
{
    .reg .pred %p;
    .reg .b32 %r<5>;
    .reg .b64 %rd<8>;
    ld.param.u64 %rd1, [a];
    ld.param.u64 %rd2, [b];
    ld.param.u64 %rd3, [c];
    mov.u32 %r1, %tid.x;
    setp.ge.u32 %p, %r1, 4;
    @%p bra DONE;
    mul.wide.u32 %rd4, %r1, 4;
    add.s64 %rd5, %rd1, %rd4;
    add.s64 %rd6, %rd2, %rd4;
    add.s64 %rd7, %rd3, %rd4;
    ld.global.u32 %r2, [%rd5];
    ld.global.u32 %r3, [%rd6];
    add.u32 %r4, %r2, %r3;
    st.global.u32 [%rd7], %r4;
DONE:
    ret;
}
"""

app = modal.App(APP_NAME)
image = modal.Image.from_registry(
    f"debian:bookworm-slim@{BASE_IMAGE_DIGEST}", add_python="3.12",
)


class CudaError(RuntimeError):
    pass


def _check(code: int, operation: str) -> None:
    if code != 0:
        raise CudaError(f"{operation} failed with CUDA status {code}")


def _gpu_compute() -> dict[str, Any]:
    cuda = ctypes.CDLL("libcuda.so.1")
    _check(cuda.cuInit(0), "cuInit")
    device = ctypes.c_int()
    _check(cuda.cuDeviceGet(ctypes.byref(device), 0), "cuDeviceGet")
    count = ctypes.c_int()
    _check(cuda.cuDeviceGetCount(ctypes.byref(count)), "cuDeviceGetCount")
    if count.value != 1:
        raise CudaError("registered canary requires exactly one GPU")

    name = ctypes.create_string_buffer(128)
    _check(cuda.cuDeviceGetName(name, len(name), device), "cuDeviceGetName")
    major, minor = ctypes.c_int(), ctypes.c_int()
    _check(cuda.cuDeviceGetAttribute(ctypes.byref(major), 75, device), "compute major")
    _check(cuda.cuDeviceGetAttribute(ctypes.byref(minor), 76, device), "compute minor")

    context = ctypes.c_void_p()
    _check(cuda.cuCtxCreate_v2(ctypes.byref(context), 0, device), "cuCtxCreate")
    allocations: list[ctypes.c_uint64] = []
    module = ctypes.c_void_p()
    try:
        host_a = (ctypes.c_uint32 * 4)(1, 2, 3, 4)
        host_b = (ctypes.c_uint32 * 4)(10, 20, 30, 40)
        host_c = (ctypes.c_uint32 * 4)()
        for host in (host_a, host_b, host_c):
            pointer = ctypes.c_uint64()
            _check(cuda.cuMemAlloc_v2(ctypes.byref(pointer), ctypes.sizeof(host)), "cuMemAlloc")
            allocations.append(pointer)
        _check(cuda.cuMemcpyHtoD_v2(allocations[0], host_a, ctypes.sizeof(host_a)), "copy a")
        _check(cuda.cuMemcpyHtoD_v2(allocations[1], host_b, ctypes.sizeof(host_b)), "copy b")
        _check(cuda.cuModuleLoadData(ctypes.byref(module), PTX), "cuModuleLoadData")
        function = ctypes.c_void_p()
        _check(cuda.cuModuleGetFunction(ctypes.byref(function), module, b"vector_add"), "cuModuleGetFunction")
        arguments = (ctypes.c_void_p * 3)(
            ctypes.cast(ctypes.byref(allocations[0]), ctypes.c_void_p),
            ctypes.cast(ctypes.byref(allocations[1]), ctypes.c_void_p),
            ctypes.cast(ctypes.byref(allocations[2]), ctypes.c_void_p),
        )
        _check(cuda.cuLaunchKernel(function, 1, 1, 1, 4, 1, 1, 0, None, arguments, None), "cuLaunchKernel")
        _check(cuda.cuCtxSynchronize(), "cuCtxSynchronize")
        _check(cuda.cuMemcpyDtoH_v2(host_c, allocations[2], ctypes.sizeof(host_c)), "copy result")
        output = list(host_c)
        if output != [11, 22, 33, 44]:
            raise CudaError("CUDA result verification failed")
        return {
            "device_count": count.value,
            "device_name": name.value.decode("ascii", "strict"),
            "compute_capability": f"{major.value}.{minor.value}",
            "operation": "u32_vector_add_4",
            "output_sha256": hashlib.sha256(bytes(host_c)).hexdigest(),
        }
    finally:
        if module.value:
            cuda.cuModuleUnload(module)
        for pointer in allocations:
            cuda.cuMemFree_v2(pointer)
        cuda.cuCtxDestroy_v2(context)


def _result(run_id: str, source_sha: str, plan_fingerprint: str,
            metrics: dict[str, Any]) -> dict[str, Any]:
    identity = {
        "run_id": run_id,
        "source_sha": source_sha,
        "plan_fingerprint": plan_fingerprint,
        "image_digest": CANARY_IMAGE_DIGEST,
        "metrics": metrics,
    }
    return {
        "schema_version": 1,
        **identity,
        "workload": WORKLOAD,
        "provider": "modal_gpu",
        "status": "passed",
        "gpu_used": True,
        "checksum": hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest(),
    }


def _canary_image_digest() -> str:
    manifest = {
        "schema_version": 1,
        "base_image_digest": BASE_IMAGE_DIGEST,
        "python": "3.12",
        "ptx_sha256": hashlib.sha256(PTX).hexdigest(),
        "gpu": "T4",
        "gpu_count": 1,
        "cpu": 1,
        "memory_mib": 512,
        "timeout_seconds": 30,
        "max_containers": 1,
        "network": "blocked",
        "modal_access": "restricted",
        "single_use_containers": True,
    }
    return "sha256:" + hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


CANARY_IMAGE_DIGEST = _canary_image_digest()


@app.function(
    image=image,
    gpu="T4",
    cpu=1,
    memory=512,
    timeout=30,
    max_containers=1,
    block_network=True,
    restrict_modal_access=True,
    single_use_containers=True,
)
def run_canary(run_id: str, source_sha: str, plan_fingerprint: str) -> dict[str, Any]:
    if (RUN_ID.fullmatch(run_id) is None or SOURCE_SHA.fullmatch(source_sha) is None or
            FINGERPRINT.fullmatch(plan_fingerprint) is None):
        raise ValueError("invalid owner-bound canary identifiers")
    return _result(run_id, source_sha, plan_fingerprint, _gpu_compute())

