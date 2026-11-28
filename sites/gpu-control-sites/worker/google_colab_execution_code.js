import { parseTrainingSource } from "./training_source.js";
import { validateTrainingManifest } from "./training_contract.js";
import { GOOGLE_COLAB_MAX_ARTIFACT_BYTES, GOOGLE_COLAB_MAX_RUNTIME_SECONDS,
  GOOGLE_COLAB_MAX_TOTAL_ARTIFACT_BYTES } from "./google_colab_execution_limits.js";

function validRunId(value) { return typeof value === "string" && /^[0-9a-f]{32}$/.test(value); }

/** Build deterministic, credential-free code for one immutable public source run. */
export function buildGoogleColabExecutionCode({ runId, repository, commit, visibility, manifest, runtimeSeconds, accelerator }) {
  if (!validRunId(runId) || !Number.isSafeInteger(runtimeSeconds) || runtimeSeconds < 1 ||
      runtimeSeconds > GOOGLE_COLAB_MAX_RUNTIME_SECONDS || !validateTrainingManifest(manifest) ||
      visibility !== "public" || !["T4", "L4"].includes(accelerator) ||
      !manifest.gpu_profiles.includes(accelerator) || !manifest.outputs.includes("metrics.json") ||
      !manifest.outputs.some((path) => /(^|\/)(checkpoint|checkpoints)(\/|$)/i.test(path))) {
    throw new Error("GOOGLE_COLAB_EXECUTION_PLAN_INVALID");
  }
  const source = parseTrainingSource(repository, commit);
  const repoUrl = `https://github.com/${source.repository}.git`;
  const config = JSON.stringify({ run_id: runId, repository: source.repository, commit: source.commit,
    repo_url: repoUrl, runtime_seconds: runtimeSeconds, entrypoint: manifest.entrypoint,
    dependency_lock: manifest.dependencies_lock, python_version: manifest.python_version,
    outputs: manifest.outputs, accelerator });
  return `# GPU Control owner-selected Colab execution. No credentials are embedded.
hashlib = __import__('hashlib')
json = __import__('json')
os = __import__('os')
pathlib = __import__('pathlib')
subprocess = __import__('subprocess')
sys = __import__('sys')
time = __import__('time')

CFG = json.loads(${JSON.stringify(config)})
ROOT = pathlib.Path('/tmp/gpu-control-' + CFG['run_id'])
RECEIPT = pathlib.Path('/tmp/gpu-control-' + CFG['run_id'] + '.receipt.json')

def emit(value):
    print('GPU_CONTROL_RECEIPT:' + json.dumps(value, sort_keys=True, separators=(',', ':')))

if RECEIPT.exists():
    emit(json.loads(RECEIPT.read_text(encoding='utf-8')))
else:
    started = time.monotonic()
    deadline = started + CFG['runtime_seconds']
    def remaining(maximum):
        value = deadline - time.monotonic()
        if value <= 0: raise subprocess.TimeoutExpired([], 0)
        return min(maximum, value)
    outcome = {'run_id': CFG['run_id'], 'repository': CFG['repository'], 'commit': CFG['commit'],
               'state': 'failed', 'exit_code': None, 'metrics': None, 'artifacts': [], 'gpu': None,
               'error_code': None}
    try:
        actual_python = f'{sys.version_info.major}.{sys.version_info.minor}'
        if actual_python != CFG['python_version']:
            raise RuntimeError('COLAB_EXECUTION_FAILED')
        gpu_info = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            check=True, timeout=remaining(10), capture_output=True, text=True).stdout.strip().splitlines()
        if not gpu_info:
            raise RuntimeError('GPU_NOT_AVAILABLE')
        if not ROOT.exists():
            subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout',
                CFG['repo_url'], str(ROOT)], check=True, timeout=remaining(120),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', '-C', str(ROOT), 'fetch', '--depth=1', 'origin', CFG['commit']],
            check=True, timeout=remaining(120), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', '-C', str(ROOT), 'checkout', '--detach', CFG['commit']],
            check=True, timeout=remaining(30), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--require-hashes',
            '-r', str(ROOT / CFG['dependency_lock'])], check=True, timeout=remaining(180),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        torch = __import__('torch')
        if not torch.cuda.is_available():
            raise RuntimeError('GPU_NOT_AVAILABLE')
        torch_gpu = torch.cuda.get_device_name(0)
        if CFG['accelerator'].lower() not in torch_gpu.lower():
            raise RuntimeError('GPU_SPEC_MISMATCH')
        outcome['gpu'] = {'name': torch_gpu, 'nvidia_smi_name': gpu_info[0],
            'cuda_available': True, 'device_count': torch.cuda.device_count(),
            'torch_version': torch.__version__, 'cuda_version': torch.version.cuda}
        process = subprocess.run([sys.executable, str(ROOT / CFG['entrypoint'])], cwd=str(ROOT),
            timeout=remaining(CFG['runtime_seconds']), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        outcome['exit_code'] = process.returncode
        outcome['state'] = 'succeeded' if process.returncode == 0 else 'failed'
        metrics_path = ROOT / 'metrics.json'
        if metrics_path.is_file() and not metrics_path.is_symlink() and metrics_path.stat().st_size <= 8192:
            try:
                metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
                if isinstance(metrics, dict): outcome['metrics'] = metrics
            except Exception:
                outcome['error_code'] = 'METRICS_INVALID'
        total_bytes = 0
        for relative in CFG['outputs']:
            candidate = ROOT / relative
            current = candidate
            unsafe_path = ROOT.is_symlink()
            while current != ROOT:
                if current.is_symlink(): unsafe_path = True
                current = current.parent
            if unsafe_path:
                continue
            output = candidate.resolve()
            if ROOT.resolve() not in output.parents or not output.is_file() or output.is_symlink():
                continue
            size = output.stat().st_size
            if size > ${GOOGLE_COLAB_MAX_ARTIFACT_BYTES} or total_bytes + size > ${GOOGLE_COLAB_MAX_TOTAL_ARTIFACT_BYTES}:
                outcome['error_code'] = 'OUTPUT_LIMIT_EXCEEDED'
                outcome['state'] = 'failed'
                break
            digest = hashlib.sha256()
            with output.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''): digest.update(chunk)
            total_bytes += size
            outcome['artifacts'].append({'path': relative, 'size_bytes': size, 'sha256': digest.hexdigest()})
    except subprocess.TimeoutExpired:
        outcome['error_code'] = 'WORKLOAD_TIMEOUT'
    except RuntimeError as error:
        outcome['error_code'] = str(error) if str(error) in ('GPU_NOT_AVAILABLE', 'GPU_SPEC_MISMATCH') else 'COLAB_EXECUTION_FAILED'
    except subprocess.CalledProcessError as error:
        outcome['error_code'] = 'SOURCE_OR_DEPENDENCY_COMMAND_FAILED'
        outcome['exit_code'] = error.returncode
    except Exception:
        outcome['error_code'] = 'COLAB_EXECUTION_FAILED'
    outcome['elapsed_seconds'] = min(int(time.monotonic() - started), CFG['runtime_seconds'] + 1)
    temp_path = RECEIPT.with_suffix('.tmp')
    temp_path.write_text(json.dumps(outcome, sort_keys=True, separators=(',', ':')), encoding='utf-8')
    os.replace(temp_path, RECEIPT)
    emit(outcome)
`;
}
