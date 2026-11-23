#!/usr/bin/env python3
"""Unprivileged CUDA Driver API probe with no network or input surface."""
import ctypes
import json

def check(code: int, operation: str) -> None:
    if code != 0:
        raise RuntimeError(f"{operation} failed with CUDA status {code}")

cuda = ctypes.CDLL("libcuda.so.1")
check(cuda.cuInit(0), "cuInit")
count = ctypes.c_int()
check(cuda.cuDeviceGetCount(ctypes.byref(count)), "cuDeviceGetCount")
if count.value != 1:
    raise RuntimeError("exactly one GPU is required")
device = ctypes.c_int()
check(cuda.cuDeviceGet(ctypes.byref(device), 0), "cuDeviceGet")
name = ctypes.create_string_buffer(256)
check(cuda.cuDeviceGetName(name, len(name), device), "cuDeviceGetName")
major = ctypes.c_int()
minor = ctypes.c_int()
check(cuda.cuDeviceComputeCapability(ctypes.byref(major), ctypes.byref(minor), device), "cuDeviceComputeCapability")
context = ctypes.c_void_p()
check(cuda.cuCtxCreate_v2(ctypes.byref(context), 0, device), "cuCtxCreate")
try:
    free = ctypes.c_size_t()
    total = ctypes.c_size_t()
    check(cuda.cuMemGetInfo_v2(ctypes.byref(free), ctypes.byref(total)), "cuMemGetInfo")
finally:
    check(cuda.cuCtxDestroy_v2(context), "cuCtxDestroy")
print(json.dumps({
    "test": "cuda-driver-canary-v1", "gpu_used": True, "device_count": count.value,
    "device_name": name.value.decode("utf-8", "strict"),
    "compute_capability": f"{major.value}.{minor.value}",
    "total_vram_bytes": total.value, "free_vram_bytes": free.value,
}, allow_nan=False, sort_keys=True))
