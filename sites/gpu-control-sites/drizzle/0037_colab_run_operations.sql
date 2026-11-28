-- Provider-specific operation journal for Colab's resumable API calls.
-- The shared gateway_delegated_plans row remains the owner-visible run ledger.
CREATE TABLE google_colab_run_operations (
  run_id TEXT PRIMARY KEY REFERENCES gateway_delegated_plans(id) ON DELETE CASCADE,
  owner_id TEXT NOT NULL,
  plan_fingerprint TEXT NOT NULL CHECK (length(plan_fingerprint) = 64),
  state TEXT NOT NULL CHECK (state IN (
    'runtime_create_pending', 'runtime_ready', 'session_create_pending',
    'execution_pending', 'execution_complete', 'cleanup_pending', 'terminal'
  )),
  runtime_request_id TEXT NOT NULL CHECK (length(runtime_request_id) = 36),
  execution_id TEXT CHECK (execution_id IS NULL OR length(execution_id) = 36),
  runtime_name TEXT CHECK (runtime_name IS NULL OR length(runtime_name) BETWEEN 10 AND 72),
  session_name TEXT CHECK (session_name IS NULL OR length(session_name) BETWEEN 20 AND 145),
  connection_ciphertext TEXT CHECK (connection_ciphertext IS NULL OR length(connection_ciphertext) BETWEEN 24 AND 16384),
  connection_iv TEXT CHECK (connection_iv IS NULL OR length(connection_iv) = 16),
  execution_code_sha256 TEXT CHECK (execution_code_sha256 IS NULL OR length(execution_code_sha256) = 64),
  execution_result_json TEXT,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (owner_id, run_id, plan_fingerprint)
    REFERENCES gateway_delegated_plans(owner_id, id, fingerprint) ON DELETE CASCADE,
  CHECK ((connection_ciphertext IS NULL) = (connection_iv IS NULL)),
  CHECK (runtime_name IS NULL OR runtime_name GLOB 'runtimes/*'),
  CHECK (session_name IS NULL OR session_name GLOB 'runtimes/*/sessions/*'),
  CHECK (execution_result_json IS NULL OR length(execution_result_json) <= 65536)
);

CREATE INDEX idx_google_colab_run_operations_owner_state
  ON google_colab_run_operations(owner_id, state, updated_at);

PRAGMA foreign_key_check;
