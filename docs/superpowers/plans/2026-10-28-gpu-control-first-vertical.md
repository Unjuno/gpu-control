# First ChatGPT CPU Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 実装担当Lunaは1タスクずつ完了させる。

**Goal:** 実ChatGPTから登録済みCPU実験を追加provider料金0ドルで実行し、再起動・cancel・別会話での結果取得を成立させる。

**Architecture:** 既存Gateway/SQLキューを拡張し、worker側のlocal Docker backendで実行する。`gateway/project_control/runner.py`のsource検証と隔離設定を再利用し、同期実行関数を永続handleで追跡できる非同期処理へ分解する。

**Tech Stack:** 既存Python/FastAPI/SQLAlchemy/PostgreSQL/Docker。新しい汎用ジョブ基盤は導入しない。

**Spec:** `docs/specs/chatgpt-native-experiment-control-plane.md`、同ディレクトリの `2026-10-28-gpu-control-roadmap.md`。

## Global Constraints

- roadmapのGlobal Constraintsをすべて適用する。基準SHAは `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`、着手時に再確認する。
- 最初は1 worker、最大同時数1、CPUのみ。GPU要求はBLOCKEDで返す。
- 運用者が明示的に有効化した `local_cpu` + 登録済みworkload + 外部課金なし + 制限内だけ事前許可する。全provider共通の承認省略フラグを作らない。
- 新規ファイル名は以下を採用する。既存mainに相当機能が追加されていたら重複を作らず計画の対応先を更新する。
- schema変更は移行・旧API互換試験と同じPRに含める。

## Review Focus

- 0ドル許可がModal/RunPodや未知providerへ広がらない（T3）。
- registry改変・旧plan・source SHA不一致が承認済み実行をすり替えない（T1/T3）。
- コンテナ作成後のworker停止、同名の別container、取消との競合（T4/T5）。
- OAuth再接続・別owner・別会話の検索（T2/T6）。
- stdoutの偽GPU情報、巨大結果、失敗後のcleanup、artifact保持（T4/T5）。

## 実装前の決定

### 1. 公開契約

新しいtools/listは次の7ツールだけを広告する。旧名は既存Web UI、comment bridge、既存クライアント向け互換ルーティングとして最低1リリース残し、移行期間と削除予定を文書化する。

| 名前 | 入力 | 出力の中心 |
|---|---|---|
| `experiment_capabilities` | `{}` | providers、registered_workloads、観測時刻/期限、実行可否/blockers |
| `experiment_prepare` | repository、commit、workload、parameters、runtime_seconds、max_cost_usd、resource_policy、requires_gpu、idempotency_key | run_id、exact plan、fingerprint、approval、blockers |
| `experiment_submit` | run_id、plan_fingerprint | queuedまたは既存runの状態 |
| `experiment_status` | run_id | execution/cleanup状態、elapsed、bounded logs、worker freshness |
| `experiment_result` | run_id | 完了結果、source、metrics、証拠、費用、cleanup。未完了はpending |
| `experiment_cancel` | run_id | durable cancel_requestedと現在状態 |
| `experiment_list` | limit、cursor、workload、repository、state、created_after、created_before | ownerで限定した一覧とnext_cursor |

prepareは `max_cost_usd="0.00"`, `resource_policy="free_first"` を既定値にする。commitは40桁hex。repository/commitは運用者registryに登録した組合せとの一致確認用で、任意コード実行を許可する入力ではない。requires_gpuは省略時workload要件から導出し、falseでもGPU必須workloadの制約は解除できない。

共通Envelope: `schema_version=2`, `status`, `human_summary`, `machine_state`, `next_allowed_actions`, `blocking_reason`。runがないblocked prepareではrun_idを捏造しない。unknown tool/JSON-RPC不正、認証失敗は正しいprotocol/HTTPエラーを維持し、すべてを200成功に変えない。

公開execution state: awaiting_approval / approved / queued / preparing / running / succeeded / failed / cancelling / cancelled / expired / unknown。cleanup state: not_required / pending / complete / unknown。`machine_state`は両者を持つ。`status`はblocked/pending/ok/errorの応答分類で、実行成功と混同しない。cleanup_pending/cleanup_completeはcleanup stateで表現し仕様文書に対応表を置く。

同じowner/keyと同じ入力は同じrun。入力変更はconflict。「もう一度実験」は新keyと任意のparent_run_id（P6）。fingerprint不一致のsubmitは409。旧submitはstored fingerprintを使う互換処理とし、stored planの改ざん検知を維持する。

### 2. 最初の実行構成

APIは既存HTTPS Gateway、DBはPostgreSQL。local workerは運用者の専用Docker/OrbStack環境からDBをpollする。Dockerはworkerだけが操作する。公開API・workloadにDocker socketを渡さない。専用workerホストのDB接続権限/ネットワーク範囲を最小化する。

最初の実containerは固定 `cpu-smoke-v1`。Python標準ライブラリで小さい数値演算とchecksumを実行し、exit codeとJSON metricsを返す。制限: network none、non-root、readonly rootfs、cap-drop ALL、no-new-privileges、1 CPU、256 MiB、32 PIDs、30秒、stdout/stderr合計64 KiB。必要なtmpfsだけ上限付きで許可する。

imageは運用者が事前buildしdigestを登録する。MCP/worker実行経路で依存を勝手にdownload/buildしない。sourceとimageの対応をbuild receiptに残し、外部source確認は既存fetch_sourcesと固定registry経由で行う。registryへ登録後にMCPが選べる。

stdout/stderrは再接続して回収できる上限付きDocker logging（local driver、max-size/max-file固定）を使う。既存runnerのlog-driver=noneとattach依存をそのまま流用しない。ログ枠を超えて先頭が失われた場合はtruncatedとし、完全な結果を取得できなければ成功証拠を捏造しない。

workerが停止しても終了する期限監督をtrusted container launcherに持たせる。計算子プロセスのtimeoutとworkerによるcontainer全体停止を併用し、期限超過時に子プロセスが残らないことを実証する。単なるworker内のtime.sleep/timeoutだけに依存しない。

## T1: データ契約と既存データの移行

**Files:** Modify `gateway/gpu_gateway/config.py`, `store.py`, `service.py`; Create `gateway/gpu_gateway/contracts.py`, `gateway/gpu_gateway/migrations.py`; Test `gateway/tests/test_contracts_v2.py`, `test_migrations.py`。

**Interfaces:**
- `PlanV2`: schema_version、repository、source_sha、workload、workload_manifest_digest、image_digest、parameters、provider、device_requirement、runtime_seconds、max_cost_usd、cost_evidence、authorization_policy_version。
- `ResultV2`: run_id、source_sha、plan_fingerprint、provider、simulation、gpu_used（boolまたはunknown/null）、device、exit_code、started_at、finished_at、runtime_seconds、metrics、artifacts、cost、cleanup。
- `migrate(engine) -> None`: version管理された冪等migration。workerとAPIで必要schema versionを検証する。
- 追加永続情報: cleanup_state、finished_at、version、attempt、submission_intent、result_manifest。旧runのfingerprintは再計算・上書きせずv1 readerで扱う。

- [ ] `test_v1_rows_survive_migration`: 旧DBのrun/owner/承認/key/fingerprintが保持され、2回migrationして変わらないことを書く。
- [ ] `test_unknown_schema_fails_closed`: 未知versionを実行しないこと、旧version結果を読めることを書く。
- [ ] `test_result_identity_is_control_plane_owned`: workload JSONに偽run_id/gpu_used/cleanupを入れても信頼フィールドを書き換えられないことを書く。
- [ ] 契約とmigrationを実装し、v1/新規v2の読取を分岐する。旧行を無根拠に新しい承認へ変換しない。
- [ ] `python -m pytest gateway/tests/test_contracts_v2.py gateway/tests/test_migrations.py -q`。SQLiteと一時PostgreSQLの両方でPASSを記録する。
- [ ] migrationとrollback互換性、移行前backupをPRへ記載してcommitする。

## T2: 7つのMCPツールと会話向け応答

**Files:** Modify `protocol.py`, `service.py`, `ci_bridge.py`（必要な旧名互換のみ）; Create `gateway/gpu_gateway/experiment_api.py`; Test `gateway/tests/test_experiment_api.py`。

**Interfaces:** `invoke_experiment(service, principal, name: str, arguments: dict) -> dict`。serviceはowner境界の単一実装を維持し、HTTP/MCPで別の実行ロジックを作らない。

- [ ] `test_seven_advertised_tools_and_legacy_dispatch`: 新7ツール、scope別visibility、旧6名の互換処理を検証する。
- [ ] `test_owner_isolation_for_status_result_list_cancel`: 別ownerで404、一覧に混入なし、取消不能を検証する。
- [ ] `test_result_pending_does_not_claim_success`, `test_gpu_required_never_falls_back_to_cpu`を書く。
- [ ] input/output schema、structuredContent、説明文、制限付きlogsを実装する。opaque cursorはownerに結びつけ、limitは既定20/最大50、UTC期間フィルタを受ける。
- [ ] `python -m pytest gateway/tests/test_experiment_api.py gateway/tests/test_protocol_validation.py gateway/tests/test_ci_bridge.py -q`でPASS。workloadエラーとprotocolエラーの期待応答を確認する。
- [ ] API仕様と互換期間を文書化しcommitする。

## T3: 0ドルCPU受付と限定した事前許可

**Files:** Modify `config.py`, `service.py`, `worker.py`; Create `gateway/gpu_gateway/admission.py`, `gateway/policies/local-cpu.json`; Test `gateway/tests/test_local_admission.py`。

**Interfaces:** `evaluate_admission(principal, plan: PlanV2, policy, now: int) -> AdmissionDecision`。decisionはallowed、approval_required、blocking_reason、policy_digest、valid_untilを持つ。APIとworkerで同じ判定を使う。

- [ ] `test_zero_cap_local_cpu_only`: local_cpuの実登録・有効な事前許可・制限内だけ0ドル可。有償providerに0ドルquoteを渡しても不可。
- [ ] `test_free_policy_revocation_before_start`: queue登録後のpolicy無効化で開始されない。既存runのcancelは通る。
- [ ] `test_idempotency_retry_and_new_run`: 同key同入力は同run、同key別入力409、新keyは新run、競合submitで1回だけqueue登録。
- [ ] `test_exact_source_and_plan_binding`: SHA不一致、manifest変更、fingerprint改ざん、承認期限切れを拒否する。
- [ ] コスト型を0以上へ拡張するが、provider区分/信頼済みcost証拠の検証と同時に導入する。workerの非demo一律quote必須処理を局所的なpolicy判定へ置き換える。
- [ ] local CPUはpolicyに基づく許可記録を保存しhuman approvalと区別する。無料でも高影響profileはこの経路に入れない。
- [ ] `python -m pytest gateway/tests/test_local_admission.py gateway/tests/test_service.py -q`でPASS、変更scopeを説明してcommitする。

## T4: 実CPU backendと結果証拠

**Files:** Create `gateway/gpu_gateway/local_backend.py`, `gateway/project_control/container_runtime.py`, `gateway/workloads/cpu-smoke/smoke.py`, `Dockerfile`, `supervise.py`; Modify `backends.py`, `registry.py`, `config.py`, `project_control/runner.py`; Test `gateway/tests/test_local_backend.py`, `test_local_backend_integration.py`。

**Interfaces:** `LocalContainerBackend.start(run: dict) -> dict`, `inspect(handle: dict) -> Observation`, `cancel(handle: dict) -> None`, `reconcile(run: dict) -> dict | None`。既存Backendの4操作を維持する。handleはworker host id、container id/name、run id、owner digest、plan fingerprint、image digestを含む。内部handleはMCPへ公開しない。

- [ ] `test_local_container_constraints`で隔離オプションと許可profileを検証する。
- [ ] `test_real_cpu_smoke_result`で実containerを実行し、exit=0、simulation=false、gpu_used=false、checks/checksum、source/plan一致を確認する。
- [ ] `test_missing_image_or_architecture_blocks`で未登録image、Mac/Linux architecture不一致を明確に拒否する。
- [ ] `test_bounded_invalid_and_missing_output`で64 KiB超過、NaN、壊れたJSON、metrics欠落を扱う。失敗でも観測事実とcleanupを保存する。
- [ ] runnerから隔離設定・検証済みsource取得の共通部分だけ抽出する。GitHub commentの認可をMCPの認可に流用しない。
- [ ] startはdetached containerを作成・起動してhandleを返す。T5のcaptureは終了証拠と制限付き出力を回収し、inspectのterminalはcleanup確認後にのみ返す。結果保存前にcontainerを削除しない。子プロセスに環境秘密やDB資格情報を渡さない。
- [ ] trusted supervisorの期限超過時exitと、worker停止中の実プロセス終了を確認する。
- [ ] `python -m pytest gateway/tests/test_local_backend.py gateway/tests/test_local_backend_integration.py -q`を専用Docker環境で実行しPASS。Dockerなしでskipなら実CPU受入はBLOCKED。
- [ ] 既存project_control試験も実行し、GitHub CPU経路の互換性を保ってcommitする。

## T5: 再起動・取消・cleanupの最小受入

**Files:** Modify `worker.py`, `store.py`, `local_backend.py`; Create `gateway/tests/test_worker_recovery.py`, `test_local_lifecycle_integration.py`。

**Interfaces:** `Observation`に後方互換のcleanup情報を追加。local backendには追加の `capture(handle: dict) -> dict | None` と `cleanup(handle: dict) -> None` を定義し、workerはcaptureした終了証拠をDB保存→cleanup→inspectによる資源不在確認→terminal確定の順に進む。captureのNoneは未終了であり成功を意味しない。cleanupはidentity一致の資源だけを冪等に削除する。既存4操作のみのbackendは旧契約（terminal inspectは解放済み）を維持し、追加操作の有無をregistryで明示する。cleanup未完了は枠を保持する。provider-neutralの完全supervisorはP2、localの期限監督はこの段階で必須。

- [ ] `test_crash_after_create_before_handle`: create直後にworkerを終了し、同じname/owner/plan/imageのcontainerだけをreconcileして二重作成しない。
- [ ] `test_unrelated_container_is_not_adopted_or_deleted`: 同名でもlabel/identity不一致ならunknown。
- [ ] `test_cancel_when_new_runs_disabled`: submit後に受付OFF、cancel後に実containerが消え、再cancelは安全。
- [ ] `test_worker_restart_during_run`: worker終了・再起動後も同run_idで結果取得できる。
- [ ] `test_result_saved_before_cleanup`と`test_cleanup_failure_holds_slot`: DB/cleanup失敗で結果を捨てず、枠を誤解放しない。
- [ ] durable intent、lease fencing、再照合、取消優先処理を実装する。reconcileがstartを呼ぶ実装を実backendに持ち込まない。
- [ ] `python -m pytest gateway/tests/test_worker_recovery.py gateway/tests/test_local_lifecycle_integration.py -q`。実プロセスを停止する統合試験を実施し証拠を保存してcommitする。

## T6: ChatGPT接続と単一CPU経路の配備

**Files:** Modify `gateway/README.md`, `.env.example`, deploy/compose設定; Create `docs/CHATGPT_SETUP.md`, `docs/CHATGPT_ACCEPTANCE.md`; Modify `auth.py`, `local_oauth.py`, `protocol.py`は互換性の実証で必要な場合のみ。

**Interfaces:** HTTPS `/mcp`、既存OAuth discovery、read/run/cancel scope、永続DB、独立worker。client固有の認証緩和や匿名実行を導入しない。

- [ ] 現在のChatGPTアカウント/ワークスペースでcustom MCP接続権限を確認し、正式な接続方法を記録する。
- [ ] endpoint→OAuth→tool discovery→read-only capabilitiesを実ChatGPTで通す。現行のprotocol version/header処理を公式仕様・実クライアント要求で検証する。
- [ ] deployment protection、token audience/resource、HTTPS origin、refresh/revocation、scope不足を確認する。DB初期化/migrationをHTTP handlerに置かない。
- [ ] 固定費と常時worker稼働条件を運用手順に記載し、local workerがsleep/offlineならcapabilitiesを実行可能と偽らない。
- [ ] `python -m pytest gateway/tests/test_http_auth.py gateway/tests/test_local_oauth.py -q`、その後実ChatGPTの認証更新と再接続を検証する。
- [ ] 本番操作に追加承認が必要なときは具体的な構成・費用・rollbackを提示し、その外部操作だけ保留する。offlineの残作業は続ける。
- [ ] 設定手順と接続証拠をcommitする。トークン・パスワード・接続文字列は記録しない。

## T7: 利用者受入とCPU版の完了判定

**Files:** Create `docs/RELEASE_MATRIX.md`, `docs/acceptance/<date>-cpu.json`; Update README/STATUS。

- [ ] 別ChatGPT会話で「追加料金なしでGPUがあれば最小smoke。なければ登録済みCPU smoke」を依頼する。GPUなし理由→CPU prepare/submit→run_idを確認する。
- [ ] 「状態を見て」「結果を見せて」でCPU、provider、source SHA、時間、metrics、cleanup、既知費用が返ることを確認する。
- [ ] 同じrequest再送で同run、新しい「もう一度」で別runになることを確認する。
- [ ] 別会話で「昨日/直前の実験」を検索する。同ownerだけ見え、複数なら候補一覧を返す。
- [ ] worker停止・再開とcancelを利用者会話から確認し、backend実資源の状態と一致させる。
- [ ] CPU_EXECUTION、MCP_CONNECTIVITY、CHATGPT_TOOL_USABILITY、RECOVERY、CANCELLATION、RESULT_RETRIEVAL、定義済みSECURITY試験の結果を記録する。GPU項目は未実施ならBLOCKED/UNCERTAIN。
- [ ] 変更に関係する既存CIをexact HEADで確認し、READMEを現在の使用方法へ更新してcommitする。

## 作業コマンドの前提

上記pytestコマンドはrepository rootから、Gateway依存が入った専用venvのpythonで実行する。最初に現行 `.github/workflows/gateway-ci.yml`、gateway pyproject/requirementsを読み、その環境構築とimport pathを再現する。既存coreのuv環境とGatewayの依存を無断で混ぜない。コマンドは実行時の環境に合わせて確定し、実行結果と一緒に記録する。

各タスクは重要な失敗を再現するテスト→実装→対象試験→必要な既存回帰→commitの順。テストをスキップした場合は理由と不足証拠を明記する。実クライアントの権限不足をmockで置き換えて完成扱いしない。
