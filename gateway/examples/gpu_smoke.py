"""Registered GPU smoke workload: finite, no network, structured bounded stdout.

Bake this file and a compatible PyTorch/CUDA build into an immutable Modal Image.
This script never needs provider credentials. It is NOT a throughput benchmark.
"""
import json
import os

import torch

config = json.loads(os.environ.get('GPU_CONTROL_CONFIG_JSON', '{}'))
steps = config.get('steps', 5)
if type(steps) is not int or not 1 <= steps <= 100:
    raise ValueError('steps must be an integer from 1 to 100')
if not torch.cuda.is_available():
    raise RuntimeError('CUDA GPU is required')
torch.manual_seed(0)
x = torch.randn(512, 512, device='cuda', requires_grad=True)
for _ in range(steps):
    loss = x.square().mean()
    loss.backward()
    with torch.no_grad():
        x -= 0.01 * x.grad
        x.grad.zero_()
torch.cuda.synchronize()
print(json.dumps({'gpu_used': True, 'device': torch.cuda.get_device_name(0),
                  'steps': steps, 'loss': float(loss.detach()),
                  'peak_memory_bytes': torch.cuda.max_memory_allocated(),
                  'torch_version': torch.__version__, 'cuda_version': torch.version.cuda}))
