"""Bounded bigram-language-model smoke test; synthetic/public text only.

Default: pure Python CPU, no dependencies/network/files. Optional PyTorch backend
runs the same loss/gradient on CPU or CUDA inside an operator-registered image.
This is a correctness smoke test, NOT a GPU speed benchmark or a useful trained LM.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time

TEXT = "small models learn from small tests. " * 3


def train(*, steps=40, backend="python", device="cpu"):
    if type(steps) is not int or not 1 <= steps <= 200:
        raise ValueError("steps must be an integer between 1 and 200")
    if backend not in {"python", "torch"} or device not in {"cpu", "cuda"}:
        raise ValueError("unsupported backend/device")
    if backend == "python" and device != "cpu":
        raise ValueError("CUDA requires backend=torch")
    vocab = sorted(set(TEXT))
    encoded = [vocab.index(c) for c in TEXT[:96]]
    pairs = list(zip(encoded, encoded[1:]))
    size, count = len(vocab), len(pairs)
    started = time.perf_counter()
    peak = 0
    if backend == "python":
        weights = [[0.0] * size for _ in range(size)]
        def loss_and_gradient():
            gradient = [[0.0] * size for _ in range(size)]
            loss = 0.0
            for x, y in pairs:
                row = weights[x]
                shift = max(row)
                exp = [math.exp(v - shift) for v in row]
                total = sum(exp)
                loss += math.log(total) + shift - row[y]
                for j in range(size):
                    gradient[x][j] += (exp[j] / total - (j == y)) / count
            return loss / count, gradient
        initial, _ = loss_and_gradient()
        for _ in range(steps):
            _, grad = loss_and_gradient()
            weights = [[weights[i][j] - grad[i][j] for j in range(size)] for i in range(size)]
        final, _ = loss_and_gradient()
    else:
        import torch
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable; no silent CPU fallback")
        torch.set_num_threads(1)
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        xs = torch.tensor([x for x, _ in pairs], device=device)
        ys = torch.tensor([y for _, y in pairs], device=device)
        weights = torch.zeros(size, size, device=device, dtype=torch.float64, requires_grad=True)
        initial = torch.nn.functional.cross_entropy(weights[xs], ys).item()
        for _ in range(steps):
            loss = torch.nn.functional.cross_entropy(weights[xs], ys)
            loss.backward()
            with torch.no_grad():
                weights -= weights.grad
                weights.grad.zero_()
        final = torch.nn.functional.cross_entropy(weights[xs], ys).item()
        if device == "cuda":
            torch.cuda.synchronize()
            peak = torch.cuda.max_memory_allocated()
    if not (math.isfinite(final) and final < initial):
        raise RuntimeError("loss did not improve")
    return {"test": "tiny-bigram-v1", "backend": backend, "device": device,
            "gpu_used": device == "cuda", "steps": steps, "training_pairs": count,
            "vocab_size": size, "parameters": size * size,
            "initial_loss": initial, "final_loss": final,
            "elapsed_seconds": time.perf_counter() - started, "peak_vram_bytes": peak}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["python", "torch"], default="python")
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--steps", type=int, default=40)
    args = p.parse_args()
    config = json.loads(os.environ.get("GPU_CONTROL_CONFIG_JSON", "{}"))
    if not isinstance(config, dict) or set(config) - {"steps"}:
        p.error("only the bounded steps parameter can be supplied by the gateway")
    # Device/backend are fixed by the operator's argv, never a submitted parameter.
    result = train(steps=config.get("steps", args.steps), backend=args.backend, device=args.device)
    print(json.dumps(result, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
