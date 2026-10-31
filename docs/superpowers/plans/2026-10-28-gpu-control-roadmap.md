# ChatGPT-native gpu-control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 実装担当はLuna。複数エージェントへの自動委譲は前提にしない。

**Goal:** ChatGPTの会話から登録済み実験を依頼し、実計算・停止・復旧・後日の結果取得まで利用できる製品にする。

**Architecture:** 既存FastAPI Remote MCP Gateway、OAuth、SQLAlchemy永続キュー、独立workerを継続する。最初は既存のCPUコンテナ実行資産を再利用するlocal CPU backendを接続し、ChatGPTとの縦通しを完成させる。実用化後に無料枠GPU、明示承認付き有償GPU、長期運用へ拡張する。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、PostgreSQL、Docker/OrbStack、OAuth/OIDC、Remote MCP。SQLiteは開発用。provider SDKはworker側だけ。

**Spec:** `docs/specs/chatgpt-native-experiment-control-plane.md`（ユーザー提供の原文）。近接実装計画は `2026-10-28-gpu-control-first-vertical.md`、引き継ぎは `2026-10-28-gpu-control-luna-handoff.md`。

## Global Constraints

- 製品の主要入口はChatGPT。初回接続と運用者設定を除き、通常の実験でCLI・Issueコメント操作を要求しない。
- `prepare`は計算資源を作成しない。`submit`はキュー登録後に返り、HTTP処理内で実験を完走させない。
- `approved=true`やモデル生成テキストは人間の承認ではない。
- `FREE_FIRST`を既定にし、GPU必須要求をCPUへ黙って変更しない。料金・quota不明は無料扱いしない。
- ツール入力からshell、image、provider endpoint、Python import先、任意Dockerfileを選ばせない。
- CPU、simulation、mock、GPU実実行の証拠を混同しない。
- owner/subject isolationを全操作、検索、成果物取得に適用する。
- 新規実行停止・承認失効後も既存資源の観測・停止・cleanupは可能にする。
- 初期リリースは単一運用者。多人数SaaS、任意コード実行、全provider実装は後続の独立判断事項。
- ローカル実行の「0ドル」は追加provider料金0ドルという意味。電力・既存PC・Gateway・DBの固定運用費が消えるという意味ではない。
- 計画は課金・本番デプロイ・権限変更・PRマージの承認ではない。実装時点の明示承認とリポジトリ規則を照合する。

## Latest status snapshot — 2026-10-31

### Live gate and current-source refresh — 2026-10-31 08:35 JST

- Rechecked the primary worktree at `a794438f42bd7246f463eaaa40d963af0aae9d13`:
  47 modified/deleted tracked paths plus 22 untracked paths. With PostgreSQL 16
  and the local CPU smoke container enabled, Gateway passed **497 tests / 2
  optional skips**; Core passed **559 / 1 Python-3.11-specific skip** under
  Python 3.12. The task-created DB container was removed and `git diff --check`
  passed. Exact inputs and scope: `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`.
- A separate #58-based P1+P3 integration candidate passed the full Gateway
  suite **432 / 2 optional skips** with PostgreSQL outage recovery and CPU
  execution enabled. Its result is recorded in
  `docs/acceptance/2026-10-31-p1-p3-integration-on-58.md`; this combined patch
  has no GitHub CI or GitHub review.
- Read-only GitHub refresh: PR #58 remains OPEN/DRAFT/CLEAN at
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4` and PR #59 remains OPEN/DRAFT/CLEAN
  at `76c2a1a1b4439cf093c4e6efdd39d5121eb08959`; both have successful recorded
  Actions/Vercel statuses but no submitted review. Production probes returned
  `/healthz`=200, `/readyz`=404, and unauthenticated `/mcp`=401. A fresh ChatGPT
  web view showed only login/sign-up controls. P1 ChatGPT acceptance remains
  NOT RUN; the selected host and workspace are not available in this session.
- Repository mode remains `parked`. No GitHub write, merge, deployment,
  provider call, or paid execution occurred. The bullets below retain earlier
  source/status details and are superseded where this refresh gives newer
  evidence.

- Refreshed 2026-10-31 after PR stack repair: local branch
  `codex/chatgpt-cpu-vertical` is at
  `a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits ahead of local
  `origin/main` (`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`). The primary
  branch and PR #51 now diverge (56/55 commits on the symmetric difference)
  after the PR-side base merge; the dirty source snapshot remains preserved.
  The current dirty worktree has 45 modified tracked
  paths plus 17 untracked paths (62 total), none staged. `git diff --check`
  passes. PR #51 is OPEN/DRAFT at
  `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`, based on current PR #57 head
  `51b88f6`; GitHub reports `MERGEABLE`/`CLEAN`, all seven required Actions
  checks and Vercel pass, and no review is submitted. The conflict repair
  retained both full Gateway integration CI jobs and explicit repository
  package installation.
- PR #58 is OPEN/DRAFT at `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, based
  on PR #51 head `e3ffcef`. Its seven required Actions contexts and Vercel pass
  on that refreshed head; GitHub reports `MERGEABLE`/`CLEAN` and no review is
  submitted. This is a focused schema-v9 OAuth follow-up, still downstream of
  the unreviewed aggregate #51. A separate read-only Security Review of the
  exact #58 head found no actionable findings in DCR consent persistence or
  schema-v9 migration; it was static review only and is not a GitHub review or
  hosted OAuth acceptance.
- Refreshed the stacked P1/P3 PRs on 2026-10-31: PR #57 is OPEN/DRAFT at
  `51b88f6` based on #56 at `34cc58c`; PR #51 is OPEN/DRAFT at `e3ffcef` based
  on #57; PR #58 remains at `561a6c7` based on #51. All seven required Actions
  contexts and Vercel pass on each current head, and GitHub reports CLEAN; no
  review decision is recorded for these PRs. P3 paired-backup/Linux operations
  is now isolated as PR #59 at `76c2a1a`, based on #57 at `51b88f6`. Its seven
  required Actions contexts and Vercel also pass; Gateway offline CI run
  `41130137786` used PostgreSQL 16 and reported 282 passed, 5 skipped, and one
  warning. PR #59 remains OPEN/DRAFT/CLEAN with no review decision. These are
  branch CI results, not target-host or ChatGPT acceptance.
- The latest full current-worktree local run recorded in
  `docs/acceptance/2026-10-31-current-snapshot-full-suite.md` passed
  Gateway **480 / 2 skipped** against pinned PostgreSQL 16 and the
  digest-identified CPU smoke image; Core passed **550 / 1 Python-3.11-specific
  skip**. Follow-up current-source PostgreSQL OAuth/migration, backup-manifest,
  and real-container worker-crash checks passed **7/7**, **1/1**, and **1/1**
  respectively. These prove local integration behavior, not hosted runtime or
  ChatGPT acceptance.
- A second exact candidate was reconstructed from PR #51's current head
  `e3ffcef` through the full local tree at `a794438` plus its dirty/untracked
  files. The candidate matched all **339 files** byte-for-byte; its Gateway
  suite passed **482 / 2 skipped**, and Core passed **559 / 1 skipped**. Exact
  patch SHA and test inputs are recorded in
  `docs/acceptance/2026-10-31-pr51-full-current-candidate.md`. This adds local
  candidate evidence, not GitHub CI/review or deployment acceptance.
- The current uncommitted-diff Security Review found no actionable findings;
  independent review of local P4 signer commits `3d82405..a794438` also found
  no Critical, Important, or Minor issues. GitHub review remains outstanding.
- A fresh read-only ChatGPT web check in the available in-app browser showed
  logged-out `Log in` / `Sign up` controls. The ChatGPT native app is blocked
  by the computer-use safety boundary. No account or workspace settings were
  changed; login/role/write-action eligibility remain unverified.
- Latest recorded public checks show production `/healthz`=200,
  `/readyz`=404, OAuth metadata=200, and unauthenticated `/mcp`=401. The
  available ChatGPT browser was logged out; the protected preview requires
  SSO. No OAuth grant, ChatGPT tool call, CPU run from ChatGPT, or
  cross-conversation result retrieval has been accepted.
- Target host, provider/region, public origin, monthly ceiling, alert route,
  and SLO remain unresolved. P4 has no accepted live GPU backend; P5 paid
  execution remains separately unauthorized. Preserve
  `policies/repository-state.yaml` at `mode: parked` and do not treat local
  checks or checks on PR #51's old head as live acceptance evidence.
- P2 local recovery evidence now includes PostgreSQL-backed worker death after
  a real Docker start, followed by same-run adoption, exact artifact retrieval,
  cleanup, and slot release. Target-host RPO/RTO and multi-operator recovery
  acceptance remain open.

This snapshot supersedes older “uncommitted/unpushed” state notes below. Dated logs are historical evidence only; refresh their external facts before reuse.

## Review Focus

1. 同じsubmitを通信再試行した場合と「もう一度実験して」を区別し、前者は同一run、後者は新runにする（P1/T3、P2）。
2. provider作成直後のworker停止、DB停止、lease競合で二重作成・無関係な資源削除をしない（P1/T5、P2）。
3. OAuth期限切れ、issuer変更、別会話・別利用者からの参照で所有権が変わらない（P1/T6、P3）。
4. 無料quotaの競合消費、期限切れ見積り、計算終了後のストレージ料金でゼロ費用を偽らない（P4、P5）。
5. 不正・巨大・欠落した結果、モデル出力に含まれる命令で制御操作や成功判定が変わらない（P1/T4、P2、P6）。

## 2026-10-28の確認済み基準

### Vercel deployment provenance refresh — 2026-10-30 14:49 UTC

Read-only Vercel API metadata confirms the production deployment is
`dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ` from `main` at
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. PR #51 has a READY preview
`dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe` at `aa681f4062dac6b73bcf380a38a4258b96a47e1`,
but it is `target=null` and SSO-protected. The production alias's
`/readyz`=404 therefore corresponds to the old production revision. No
authenticated preview fetch was made because the available fetch operation
creates/reuses a temporary share link; no authorization was given. This is
deployment-provenance evidence only, not readiness or ChatGPT acceptance.

GitHub APIで確認したmainは `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`。実装開始時に更新する。

| 対象 | 確認内容 | 計画への影響 |
|---|---|---|
| `gateway/gpu_gateway/protocol.py` | `integrations_list`と`experiments_*`計6ツール、structuredContentあり | 既存動作を再利用し、安定した7ツールへ整理 |
| `service.py`, `store.py`, `worker.py` | owner/key制約、fingerprint承認、SQLキュー、lease、曖昧submitのreconcileあり | 全置換しない。migrationと耐障害性を補強 |
| `service.Prepare` / `prepare()` | cap=0を拒否し、全runがawaiting_approvalへ入る | 登録済み低リスクCPUの0ドル経路を追加 |
| `config.Workload` | max_costとquoteが正値、GPU既定T4、provider固定 | CPU・ゼロ費用・source identity・後続の複数候補を明示モデル化 |
| `backends.py`, `registry.py` | Demo、Modal Sandbox、RunPod factory bridge | 実CPU backendを追加。RunPod bridgeは実運用の完成品ではない |
| `gateway/project_control/` | GitHub Issue #48経由の実CPU隔離runnerあり | source検証・固定container profileを再利用。同期executeをそのままMCP内で呼ばない |
| `auth.py`, `local_oauth.py` | 外部OIDCと内蔵single-owner OAuth | 新認証を作り直さず、実ChatGPT接続と更新・失効を検証 |
| `policies/repository-state.yaml` | parked、有償実行無効 | CPU経路と有償activationを別の審査範囲にする |
| PR #43 | Draft/Open、head `1699b75df8262023501d41279e83bf429dca1be4`、35ファイルの監査修正 | 先の「open PRなし」は誤り。mainとの対応表をP0で作る |
| main branch API | 初回監査時は`protected=false`（2026-10-28 09:43 UTC）。09:44 UTCに保護設定し、APIで再確認済み | 現在はPR、1 approval、7 GitHub Actions checks、会話解決、linear/up-to-date履歴を必須化。詳細は`docs/BASELINE_AUDIT.md` |

PR #43の説明にはHTTP/期限/復旧/配布物の修正とCI結果がある。ただし本計画ではCIを再実行していない。PR本文の過去の成功を現在mainの受入証拠にしない。READMEには古いSHA・transport説明が残り、`docs/STATUS.md`や実装と不整合がある。

このフォルダはGit checkoutではなく計画書の保存場所。実装担当は本体を取得し、これらの文書を本体へ取り込む。今回アプリ実装、環境変更、課金実行は行っていない。

### P0 GitHub保護ゲート更新（2026-10-28 09:44 UTC）

初回監査で`main`が無保護だったため、GitHub APIでmain branch protectionを設定し再取得した。PR必須、1名承認（最新push担当者以外）、stale review dismissal、会話解決、linear history、strict status checks、admin enforcement、force-push/deletion禁止を確認。必須checkは現在のPR #51 headで実在・成功を確認したGitHub Actions app ID 15368の7 job（Python 3.11/3.12/3.13、Trusted reference container、Gateway offline tests、Gateway comment bridge tests、Project bridge tests）。PR #51は依然OPEN/DRAFTかつ`REVIEW_REQUIRED`で、ローカル111 dirty pathsはremote checks対象外。これでmain保護の前提のみ満たした。ChatGPT workspace、P1接続、P3 host/provider/region/cost ceiling/notification SLO、P4 live GPU、P5 paid authorityは未確定または未受入のためparkedを維持する。

## 完成の段階と依存関係

```text
P0 現行基準・接続条件確認
 └─ P1 ChatGPT→実CPU→結果（最初の利用可能版）
     └─ P2 復旧・停止・成果物の堅牢化
         └─ P3 継続運用・CPU安定版
             └─ P4 資源選択と最初の実GPU
                 └─ P5 承認付きRunPod有償実行
                     └─ P6 再現可能な比較実験
                         └─ P7 保守運用と追加provider
```

外部アカウント設定待ちでも独立したoffline実装は進める。ただしP1のChatGPT実受入前に複数providerの実装へ拡散しない。将来段階は着手直前にAPI・規約・費用・実コードを再確認して詳細計画を更新する。

期間はLunaの処理時間ではなく、人間のレビュー・外部設定を含む計画上の目安。P0〜P1で2〜4週間、P2〜P3で追加3〜5週間、P4〜P5で追加4〜8週間、P6〜P7を3〜6か月の拡張期間とする。暦で強制終了せず受入条件で判定し、最初の2PRの実績で見積り直す。

## 2026-10-28 継続時点と直近の実行順

### 継続ゴールの現在状態 — 2026-10-28 11:49 UTC

Codex goal is active for the complete Unjuno/gpu-control roadmap: make
registered experiments usable from ChatGPT through real CPU execution and
result retrieval, then complete recovery/operations, GPU, and separately
authorized paid execution. This plan does not authorize deployment, spending,
permission changes, or merging.

Current checkout: `codex/chatgpt-cpu-vertical` at
`f054aebe96460fe033dde8d91d7e3bbab0255655`; 75 tracked modified/deleted plus
42 untracked paths (117 total), none staged. The ownership map in
`2026-10-28-gpu-control-worktree-slices.md` matches those 117 paths. Existing
Codex Security results refer to earlier snapshots; they do not establish
coverage of the exact current 117-path snapshot. `git diff --check` passes.
Repository policy remains `mode: parked`.

The current external acceptance gate is still unavailable in this session:
ChatGPT and Platform opened logged out, so no intended workspace, custom MCP
write-action permission, tunnel association, or OAuth access was inspected.
The review workflow's earlier single-choice request (Bugbot or Security Review)
also remains unanswered; do not infer that choice from this continuation.
Until those gates are resolved, keep the branch unmerged and focus on preparing
the exact reviewable snapshot and the independent acceptance checklist.

Next order: (1) settle and execute the selected current-diff review, (2) obtain
the user's actual ChatGPT/Platform workspace path and complete the real CPU
vertical acceptance, (3) select and separately authorize P3 host/region/public
origin/cost ceiling/alert route and SLO, (4) validate target-host recovery and
seven-day CPU operation, and only then (5) enter P4 GPU validation. P5 remains
subject to a distinct explicit spending authorization. Detailed prerequisites
and evidence boundaries below remain normative.

この計画は長期目標を示す。以下の現状スナップショットと未解決ゲートを更新してからLunaへ渡し、各段階の受入条件を満たす順に実装する。

- GitHub `main`: `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`。2026-10-28再確認時、Draft PR #51 `codex/chatgpt-cpu-vertical` はhead `f054aebe96460fe033dde8d91d7e3bbab0255655`、121 files（+13,040/-215）、baseは上記main。現headのGitHub Actionsは4 workflowすべてsuccess（CI `40614634054`, Gateway offline `40614633953`, Gateway comment bridge `40614633965`, Project bridge `40614633942`）。PR reviewとinline review threadsはいずれも0件。Vercelの最新PR preview (`dpl_DFmSmWfMKE2Nbox5ufWDxKBa7Y9p`, target `null`) はREADY buildだが、read-only runtime checkは `/healthz`=200 with `configured=false/auth_configured=false`、`/readyz`=503、OAuth protected-resource discovery=503 `configuration_required`。ChatGPT受入には使えない。過去のCodex Security base-to-head reviewはsource scope onlyであり、GitHub reviewや今回のworking-tree security diff scanとは別証拠。working-tree scan `aec1bbb8-88e6-436d-a91b-cd21dc533413` は固定した未コミット差分の13 source filesをレビューし、0 findingsで完了した。ブランチはorigin/mainより60 commit ahead。統合前にGitHub reviewと、独立レビュー可能なslice境界を確認する。
- ローカル証拠: P1のT1-T5 CPU lifecycleとHTTP/MCPを通した実Docker実行、P2のrecovery/paired backup restore、およびP4のoffline capability/selection契約が実装・限定scopeで検証済み。これらは実ChatGPT受入、production復旧、GPU実行を意味しない。
- 公開先: Vercel `gpu-control` のproduction aliasは上記main SHAのまま。2026-10-28の公開alias確認は `/healthz=200`, `/readyz=404`, 未認証`/mcp=401`。P1実装は未公開。Vercel projectのroot外source include設定と実buildも未確認。
- 2026-10-28 04:54 UTC live read-only recheck: public alias returned `/healthz` 200 with configured local OAuth, `/readyz` 404, and unauthenticated `/mcp` 401. This confirms liveness and the unauthenticated boundary only; deployed revision, readiness, OAuth grant, and ChatGPT tool acceptance remain unverified. See `docs/CHATGPT_SETUP.md`.
- 運用先: P3 decisionは専用Linux + systemd API/worker/recovery + managed Neon + 固定artifact filesystem + TLS proxy。ホスト/provider、region、公開HTTPS origin、月額cost ceilingは未決であり、購入・本番変更は未承認。Neon production schemaは未移行で、既存OAuth admin/session stateを保全する必要がある。
- 安全ゲート: `policies/repository-state.yaml` は `mode: parked`。有償compute、RunPod live call/adapter/workflow、一般外部container実行は無効のまま維持する。コード変更・dry run・repository accessはactivation承認ではない。

直近の順序:

1. **PR #51のレビューとCI follow-upを得る。** GitHub reviewとinline review threadsは未着。過去の43 changed paths source reviewおよび今回の未コミット差分レビューはいずれも限定scopeのCodex Security結果で、GitHub reviewの代わりにはならない。Actions checksはsuccessだが、最新Vercel preview runtimeは未構成（`/readyz` 503、OAuth metadata 503）。PR #43との差分を再照合し、レビュー指摘があればhead SHAを固定して対応・再CIする。mainへの直接反映、merge、parked解除を含めない。
2. **実ChatGPT接続条件を確認する。** 利用者が使うworkspaceでcustom MCP write actionsが可能か、OAuth app接続・tool discovery・tool callを確認する。Public HTTPSのP3 hostが未決でも、Platform側のSecure MCP Tunnel権限（Tunnels Read + Manage / Read + Use）とworkspace associationが整えば、local Gatewayへ接続して短いCPU smokeを先行できる。Tunnelの120秒request deadline・10 MiB envelope上限内であることを記録し、これは開発時のChatGPT接続証拠に限定する。公開配布、継続運用、7日観測、大容量artifact受入には数えない。権限やworkspace設定が揃わなければ具体的なBLOCKED条件を記録し、独立してできる実装を進める。
3. **P3 host choiceを閉じる。** 月額上限、region、host/provider、public HTTPS originを確定してから運用構成をdeploy可能なrunbookにする。ホスト購入やproduction変更は明示承認後のみ。
4. **隔離先でproduction形状の導入を検証する。** migration、Neon互換backup/restore、artifact volume、service restart/mount/permission、TLS/proxy、monitor/alertを実測し、既存OAuthとowner境界を確認する。production schema変更は別途レビューと承認後。
5. **レビュー・CI後に実CPU verticalをdeployしChatGPT acceptanceを実施する。** 別ChatGPT会話でprepare/submit/status/result/search/artifact/cancel、worker restart、owner isolationを記録する。実ChatGPT・実ホスト証拠が揃うまで各軸をUNCERTAIN/BLOCKEDに保つ。
6. **P3の安定運用期間を測る。** seven-day observation、target-host cancellation/recovery、second-operator restore、measured RPO/RTO、capacity alert deliveryを完了する。
7. **その後P4→P5→P6→P7へ進む。** 最初の実GPU backendを選ぶ際に現行provider/API/規約/quota/pricingを再確認し、free GPUとpaid GPUは別release axisとする。P5 paid executionは別の明示authorizationを要する。

2026-10-28 continuation note: Audited the local OAuth configuration example against `Settings.web_auth_ready`, `Auth.__init__`, and `LocalOAuth`. Built-in single-owner OAuth stores opaque sessions in PostgreSQL and does not use Fernet; `GATEWAY_COOKIE_KEY` is required only for external OIDC browser login and must be generated in Fernet format. The API env example, Gateway README, OPERATIONS instructions, deploy-unit regression assertion, and implementation progress record were corrected. The initial pytest collection failure was resolved by syncing locked Gateway runtime dependencies offline and restoring pytest per `requirements-test.txt`. Current ordinary local tests: Gateway 289 passed / 9 skipped, root 532 passed / 1 skipped, focused deploy units 14 passed; compile and diff checks passed. Docker/PostgreSQL integration skips mean this run is not a fresh integration rerun; the existing separate PostgreSQL 16 + digest-pinned image acceptance remains separately scoped. Added host-independent capacity alert bridge contract at `docs/specs/capacity-alert-bridge-contract.md`; no sink was selected or configured. Provider, region, budget, public origin, recipient/SLO, and workspace write-action eligibility remain unresolved; no infrastructure, live OAuth, production DB, or paid resource was changed.

### 現在の未コミット差分を分けるレビュー単位

PR #51は現在121 files（+13,040/-215）の大きな差分である。既存のslice commit群を根拠に独立レビュー済みと扱わない。各境界をcurrent HEADに対してレビューし、統合前に現行CIと個別レビューを得る。production受入には使わない。

| 順 | 独立レビュー単位 | 主な範囲 | 必須の境界・証拠 |
|---|---|---|---|
| A | 外向きHTTP境界 | `src/gpu_control/http_security.py`, `source.py`, RunPod transport helpersと各adapter tests | redirect、圧縮、body上限、permit/price freshness。offline証拠のみ。RunPod live呼び出し禁止のまま |
| B | Local CPU backend + MCP vertical | `gateway/gpu_gateway/{app,config,contracts,experiment_api,local_backend,worker}.py`、CPU workload/Docker、各 lifecycle/MCP tests | exact source/image/plan binding、idempotency、worker/recovery/cancel、owner-scoped result/artifact。real Docker/Postgres local scope |
| C | OAuth state and migration | `auth.py`, `local_oauth.py`, `migrations.py`, `owner_migration.py`と関連tests/acceptance | PKCE、refresh/revocation、旧schema/issuer保全、rollback/owner境界。synthetic isolated DB scope |
| D | Artifact・backup・host operations | `artifacts.py`, `backup_generation.py`, capacity monitor、systemd/Compose、`docs/OPERATIONS.md`とrestore/deploy tests | atomic paired backup、別DB restore、quota/mount/service/security境界。target-host/production証拠とは分離 |
| E | Capability/selection contract | `workloads.py`, `capabilities.py`, `selection.py`、P4 Gateway mapping/spec/tests | workload適合性、cost evidence freshness、unknown/free/paid分類。offline evidenceのみ、GPU実行は未受入 |
| F | CIとrelease evidence | 4 workflow files、package metadata/tests、baseline/acceptance/release/progress docs | PR/merge_group checks、wheel packaging、現行HEADでのCIとreview。CI定義だけの静的確認を実行成功扱いしない |

依存関係: AはCやBと別レビュー可能。BはCのOAuth contract/schema境界とDの永続artifact運用に依存する。EのselectionをBのprepare/submit実行へ接続するのは独立レビュー後にする。Fは各sliceの内容に応じて同時または最後に更新する。docsの同一記述はそれぞれのsliceへ含め、別の巨大docs-only PRにしない。最初にworktree上で差分内容とテスト結果の対応を監査し、ファイル境界が衝突する箇所（とくに`IMPLEMENTATION_PROGRESS.md`, `RELEASE_MATRIX.md`, `gateway-ci.yml`）は1つのowner sliceに割り当てる。

各段階はimplementation progressとrelease matrixに、実行した日時、base/control-plane SHA、環境、観測、artifact path、証拠scope、失敗・未確認事項を追記する。unit/offline/local Docker/production/ChatGPT/real GPUの証拠を混ぜない。

## P0: 現行基準を揃える（1〜2 PR）

- [x] mainとPR #43の正確なSHAを取得。各監査修正を「mainに存在／未適用／後続で置換／要調査」に分類する。2026-10-28再確認でもmainは`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`、PR #43はOPEN/DRAFT、head `1699b75df8262023501d41279e83bf429dca1be4`。
- [x] `docs/BASELINE_AUDIT.md`に対象ファイル、根拠、再現テスト、適用順序を記録する。PR全体を無条件にcherry-pickしない。
- [x] README/STATUS/実コードの相違を修正し、Gatewayとcoreの責務を記録する。
- [ ] 利用予定ChatGPT workspaceでcustom MCPのwrite actionsが利用可能か確認する。Business/Enterprise/Eduのweb workspace、作成・試験者・publisherの権限、`Create plugins with MCPs`、run/cancel action controls、tool-snapshot revisionを記録する。現行Plugins体験ではDeveloper Modeを先に有効にする必要はない。Businessはadmin/ownerのみcreate/publish可、Enterprise/Eduはadmin/ownerまたはRBAC許可memberがcreate/test可で、publishはadmin/ownerのみ。Proのread/fetch-only接続はrun/cancel受入条件を満たさない。ChatGPT側のwrite confirmation promptが出た場合の表示/応答も記録するが、server-side authorizationの代用にしない。詳細は[OpenAIの接続要件](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)を参照する。HTTPS endpointまたはSecure MCP Tunnel、OAuth、永続DB、常時workerの既存構成も調査し、不足を具体名で記録する。
  - 2026-10-28 official-doc refresh: The current OpenAI guide confirms Business and Enterprise/Edu on ChatGPT web for full MCP/write actions; Enterprise/Edu can RBAC-authorize selected creators/testers, but workspace publishing remains admin/owner-only. The current Plugins flow says Developer Mode is not required, uses Plugins → + → Add custom MCP server, and permits public HTTPS or Secure MCP Tunnel endpoints. Published tool snapshots do not auto-update; a workspace admin must refresh/review changed actions, with new actions disabled by default in the documented action-control flow. ChatGPT may ask for confirmation based on action context; this is not the Gateway's authorization evidence. The previous Developer Mode guide URL redirects to this canonical current page. This resolves the requirements, not the user's actual plan, role, settings, or connection acceptance.
  - 2026-10-28 Secure MCP Tunnel guide refresh: private server testing is supported via an outbound `tunnel-client`; requires separate Platform Tunnels Read + Manage / Read + Use permissions and association with the intended ChatGPT workspace. Documented request deadline is 120 seconds and serialized envelope limit is 10 MiB. This creates a possible bounded development smoke before public-host selection, not public distribution or continuous-operation evidence. See `docs/CHATGPT_SETUP.md`.
- [x] PR #43からCPU/MCP公開にも関係するHTTP境界・dependency修正を選択的にローカル実装し、回帰根拠を記録した。これはPR #43のmerge/cherry-pickやlive provider acceptanceを意味しない。RunPod固有の残項目はP5で追跡する。
- [ ] 独立レビュー可能な小さいPRに分割し、各headでGitHub reviewと最新CIを得る。PR #51–#59はOPEN/DRAFTでGitHub review未提出。#52はmain向けで`REVIEW_REQUIRED`。PR #58 head `561a6c7`は現在のschema-v9 OAuthコードと7 path中6 pathの最終内容が一致し、次のローカル候補の最良基底。完全候補は340ファイル一致で再構成され、#58との差分は61 path。6 slice (P1 7, P2 2, P3 11, P4 9, P5 11, cross-cutting/CI 21) を順に適用して完全一致を確認した。Focused testsはP1 56、P2 crash recovery 1、P3+P4 48、P5 Gateway 77/Core 38 pass。Full suiteは同一コードtree上でGateway 482/2 skipped、Core 559/1 skipped。P3とP4は過去のP3単独full-suite失敗を解消するため併せた候補とする。詳細なpatch fingerprintsは`docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`、実施範囲は`docs/acceptance/2026-10-31-pr51-full-current-candidate.md`。これらはローカル evidenceで、各headのGitHub CI/独立review、deployed readiness、ChatGPT acceptanceの代用ではない。GitHub PR操作やpushは未実施。
  - 2026-10-30 16:04 UTC: Materialized twenty local-only stacked refs at existing checkpoints from `codex/gpu-control-p1-01-baseline` through `codex/gpu-control-stack-20-foundation-evidence` (`f054aebe`, 121-path foundation). Exact bases, heads, path counts, and existing test evidence/gaps are in `2026-10-28-gpu-control-worktree-slices.md`. They remain unpushed; required per-head GitHub CI and independent review are still open.
  - 2026-10-31 02:22 UTC live refresh supersedes the PR status/base snapshot above: PRs #51–#59 are OPEN/DRAFT; each has nine successful rollup entries (seven Actions checks, Vercel deployment, and Vercel Preview Comments), #52 has `REVIEW_REQUIRED`, and the others have no review decision. PR #43 is OPEN/DRAFT with five successful Actions checks and `REVIEW_REQUIRED`. The current checkout is `a794438f42bd7246f463eaaa40d963af0aae9d13` with 91 changed/untracked paths; reconcile that exact tree against the PR stack before preparing new review boundaries. Production probes returned `/healthz`=200, `/readyz`=404, unauthenticated `/mcp`=401. The current local FastAPI app defines `/readyz`; the deployed 404 is a source/deployment mismatch, not a missing local handler. Full read-only evidence and Luna handoff: `docs/CHATGPT_ACCEPTANCE.md` and `docs/superpowers/plans/2026-10-28-gpu-control-luna-handoff.md`. File-by-file PR reconciliation (6 exact blobs, 39 divergent same-path files, 46 unassigned paths) and the 219-path current-tree replay artifact/hash are recorded in `docs/acceptance/2026-10-31-pr-stack-reconciliation.md`.

完了条件: 採用基準SHA、差分表、接続条件、最初のCPU workloadが確定。接続権限がなければMCP_CONNECTIVITYをBLOCKEDと記録し、backend実装まで進める。

## P1: ChatGPTから実CPUジョブを使う（7タスク、4〜7 PR）

詳細は `2026-10-28-gpu-control-first-vertical.md`。

- [x] 現行DBから移行可能なversioned plan・状態・結果契約を導入する。
- [x] `experiment_capabilities / prepare / submit / status / result / cancel / list`を公開する。
- [x] trusted registryのCPU workloadを0ドルでprepareできるようにする。低リスクの事前運用許可を厳密に限定し、有償承認は維持する。
- [x] 既存project_controlの検証・隔離を再利用するlocal Docker CPU backendを独立workerへ接続する。

- [x] 完成判定前のローカル候補準備を閉じる。2026-10-31時点でPR #58 head `561a6c7`を基底に62 worktree entriesを6 sliceへ割り当て（うち1 pathは同一内容、net 61 tree changes）、全340ファイルのexact-source replay、candidate suite、既存PR stack/CI/review状態、readiness実装・テスト・security review範囲を照合し、acceptance記録を更新した。再現手順とhashは`docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`、全体suiteは`docs/acceptance/2026-10-31-pr51-full-current-candidate.md`。これはローカル候補準備の完了であってP1製品受入ではない。最新の公開本番は`/healthz`=200、`/readyz`=404、未認証`/mcp`=401。PR #52/#58の7必須checksとVercelは成功するがDraft・未レビューで、dirty local candidateはそのCIに含まれない。認証済みChatGPT/OIDC、CPU実行、別会話からの結果取得は未受入。workspace権限と運用host/endpointが必要な受入れを進めるには、その環境への認証済みアクセスおよび選定済み運用先が要る。
- [x] process/containerの実行証拠、source SHA、image digest、fingerprint、metrics、cleanupを返す。
- [x] 同じkeyの再送、再実験の新key、owner別検索、worker再起動、cancelを実containerで確認する。
- [ ] 実ChatGPTで初回接続・実行・別会話での検索・結果取得を行う。
  - 2026-10-28 05:53 UTC live alias recheck: `/healthz`=200 with configured local OAuth and protected-resource discovery=200 advertising read/run/cancel scopes, but `/readyz`=404. This indicates the public alias still lacks the P1 readiness route; deployed SHA, durable services, OAuth grant, and ChatGPT tool execution remain unverified. PR #51 is still OPEN/DRAFT with zero reviews/threads; local worktree changes are unpushed. See `docs/CHATGPT_ACCEPTANCE.md`.
  - Local OAuth now advertises RFC 7009 revocation and binds refresh/access credentials to a persisted grant family; a v6-to-v7 additive migration preserves existing tokens. This is local protocol evidence only and does not establish live ChatGPT acceptance.
  - 2026-10-28 current-worktree revalidation: corrected three real-container integration fixtures to include the required artifact probe directory, then ran the full Gateway suite against digest-pinned CPU Docker and disposable PostgreSQL 16: 296 passed / 2 optional Torch/Modal skips. Worker-crash-after-start and PostgreSQL-outage-after-terminal-capture recovery each pass. Root suite: 532 passed / 1 skipped. This is local execution evidence; real ChatGPT connection, deployment, and cross-conversation retrieval remain NOT RUN. See `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
  - 2026-10-28 registry revalidation follow-up: local CPU plans are rechecked against the current operator workload manifest at prepare and submit; the worker now reloads configured workload JSON/file immediately before start and refuses the queued plan if source SHA, image digest, manifest digest, runtime, profile, or parameter schema changed. Missing, unreadable, or invalid configured registry now fails closed before backend start; exact manifest drift is separately reported. Focused local-admission tests: 16 passed; experiment API, local MCP, local Docker lifecycle and PostgreSQL lifecycle modules: 23 passed / 3 skipped (prebuilt CPU image and dedicated PostgreSQL integration container unavailable). No ChatGPT or production-host acceptance is implied.
  - 2026-10-28 result identity follow-up: the worker finish gate now requires provider and image digest to equal the persisted plan for every provider, not only `local_cpu`. Regression coverage confirms wrong/missing image and provider substitution terminalize as `result_integrity_failed`; the v2 schema remains backward-readable for existing results, while the new-run finish gate is strict. Evidence: `docs/acceptance/2026-10-28-result-plan-binding.md`.
  - Docker/PostgreSQL revalidation after this binding change: the full Gateway suite passed **351 tests / 2 optional Torch/Modal skips** using the digest-pinned CPU image and PostgreSQL 16 on fixed loopback `127.0.0.1:55545`. The disposable DB container, anonymous volume, and run-labeled CPU containers were absent after cleanup. Evidence and exact identities: `docs/acceptance/2026-10-28-result-plan-binding.md`. This closes only local CPU integration for this code state, not ChatGPT or production acceptance.

最初のworkloadは標準ライブラリだけの決定的 `cpu-smoke-v1`。次に既存 `orbitune-tokenizer`を接続する。GPU必須入力にCPUを自動実行しない。CPUが許可された要求のみ0ドル経路を使う。

完了条件: 別ChatGPT会話からコード/CLI操作なしで実CPUのrun_id・結果を取得できる。実行中worker再起動とcancelの証拠があり、simulation=false / gpu_used=falseを返す。

## P2: 障害時にも取りこぼさない（3〜5 PR）

主な変更先: `worker.py`, `store.py`, 新規 `lifecycle.py`, `supervisor.py`, `artifacts.py`, `gateway/tests/`。

- [x] allocation前のintentをDBに永続化し、provider/owner/run/attempt/planを結びつける。API再送・worker lease更新・再照合の責任を明記する。
- [x] 実行状態とcleanup状態を分離する。プロセス終了後もcleanup未確認なら資源枠を解放しない。cleanup失敗で結果を消さない。
- [x] 独立supervisorがtimeout、cancel、worker heartbeat切れ、cleanup_pendingを処理する。DB/worker停止中も効く実行期限を各backendに設ける。
- [x] create直後、handle保存直前、結果保存直後、cleanup直前に停止するfault injection試験を作る。DB一時停止、二重worker、遅いprovider、lease期限超過を含む。
- [x] unknownを再submitせず、完全に識別できる既存資源へ再接続する。不在が証明できない場合はUNKNOWNを保持する。
- [x] 小さい結果JSONはDB、ファイル成果物はowner管理の保存先へ分離。最初の上限案は1 runあたり10 MiB、JSON/ログ各64 KiB。巨大checkpointは未対応と返す。
- [x] artifactはdigest/size/media type/expiryを記録。任意pathやURLを直接読む機能を作らず、期限付き取得はowner照合後だけ許可する。

完了条件: 指定した各停止点で資源重複0件、他runの削除0件、既存結果消失0件。成功・失敗・cancelのすべてでcleanupの証拠が取れる。provider完全障害時はUNKNOWNと最後の観測時刻を正しく返す。

## P3: 放置しても運用できるCPU安定版（3〜4 PR）

主な変更先: `gateway/docker-compose.yml`, deploy設定、DB migration、`docs/OPERATIONS.md`, `docs/CHATGPT_ACCEPTANCE.md`。

- [ ] 本番Gatewayと独立workerの構成を1つ選び、TLS、永続PostgreSQL、migration、worker自動再起動を整える。APIにDocker socketやprovider secretsを渡さない。
  - Topology decision recorded 2026-10-28: dedicated Linux host with separate systemd API/worker/recovery services, existing managed Neon PostgreSQL, fixed-size artifact filesystem, and loopback API behind TLS proxy. Host/provider, region, cost ceiling, and public origin remain undecided; this is not purchase/deployment approval. See `docs/decisions/2026-10-28-p3-deployment-topology.md`.
  - Local systemd templates and their syntax/security checks exist; they are not installed or exercised on the selected host. Host boot, TLS proxy, permissions, mount ordering, and restart behavior remain acceptance gates.
  - 2026-10-28 local template hardening: API, worker/supervisor, migration, and capacity use separate UIDs; worker/supervisor intentionally share the worker UID. API `ReadWritePaths` is limited to the sticky probe directory; worker/supervisor can write artifact content. Artifact directories/blobs use 02750/0640 for service-group reads. Common DB/workload settings, API-only cookie/OIDC settings, capacity-only path/headroom settings, and optional worker-only provider secrets remain separate environment files. A root-only, dry-run-first artifact permission migration utility is now covered by eight safety tests, including refusal to make unknown filenames group-readable. See the isolated Linux revalidation below; current UID/mount/permissions still need verification on the selected host.
  - 2026-10-28 isolated Linux revalidation: systemd 252.39 accepted all six templates in a disposable Debian 12 container, and real UID/GID filesystem probes passed the expected API/capacity/worker/migration access matrix. This validates Linux mode bits but not service sandbox mount filtering or the selected host. Evidence: `docs/acceptance/2026-10-28-systemd-uid-boundary.md`.
  - Offline `systemd-analyze security` review reduced reported exposure estimates from 7.6 to 3.8 for API/worker/supervisor/migration and 3.0 for capacity after adding proc/device/capability/syscall/address-family controls. These are systemd directive heuristics, not vulnerability scores or live acceptance; full Gateway suite is now 284 passed / 9 skipped. Docker daemon socket authority and target-host execution remain explicit boundaries.
  - Gateway CI now invokes a guarded Linux-only helper to verify all six units with `systemd-analyze verify`; the helper itself passed in isolated Debian 12/systemd 252.39. The current worktree has not been pushed, so no GitHub Actions run covers this addition yet.
  - 2026-10-28 permission-boundary correction: source audit found `check_artifact_capacity.py` only uses mount metadata and `statvfs`; the create/write/fsync/unlink probe is API-only. Removed the unnecessary `gpu-control-artifact-probes` membership from capacity, worker and supervisor. API alone needs the supplementary group; worker owns the probe directory by UID. The earlier mode-bit test accurately recorded that the broader capacity grant allowed probe writes, but that result is superseded. A fresh Debian 12 UID/GID mode-bit matrix passed API probe/read, capacity blob-read/probe-write-denial, worker owner access, migration read denial, and API root/blob write denial; deploy-unit tests passed 14/14 and systemd 252.39 accepted all six current unit/timer templates. Target-host sandbox/mount verification remains open.
  - Upgrade notes now cover migration from the earlier shared `worker.env`: split values by service, preserve cookie/DB credentials, avoid copying provider secrets into the common API-readable file, and retain the old root-only file through rollback. No target host installation has been observed.
  - A worker/supervisor-only optional `worker-secrets.env` path now supports future provider credentials without exposing them to API, migration, or capacity services. It remains absent while providers are parked; no provider credentials or enablement were added.
  - Target-host acceptance must inspect both installed unit directives and the running processes' environment **names only**: reject provider credentials in API, DB/auth/provider values in capacity, and API/provider credentials in migration; ensure worker/supervisor receive only reviewed backend/cleanup credentials. Never print or store values. `docs/OPERATIONS.md` and `docs/CHATGPT_ACCEPTANCE.md` now include this gate.
  - 2026-10-28 local follow-up: capacity timer output now includes a stable `status=alert|ok` on every run and is defined by `gateway/deploy/capacity-event.schema.json`. The systemd unit writes stdout/stderr to journald under `gpu-control-capacity` for a stable bridge selector. Regression tests validate both states and reject an alert with missing reason or a false recovery; all six current systemd unit/timer templates, including journald directives, passed `systemd-analyze verify` in a disposable Debian 12 container using the guarded CI helper. This makes the host journal/metrics bridge contract explicit; no notification sink is configured and delivery remains a target-host acceptance gate.
  - 2026-10-28 read-only provider shortlist: Lightsail offers Tokyo and Singapore. A 2 GB VM plus a 32 GB separate artifact disk is currently estimated at $15.20/month; 4 GB plus that disk at $27.20/month, before snapshots, transfer overage, tax, domain, or backup costs. Singapore is the first region to measure against the existing Singapore Neon database; Tokyo remains an alternative. DigitalOcean is a Singapore-only comparison for this shortlist and lacks a currently listed Japan datacenter. These are candidate prices, not a selected provider or approved budget. The owner-set cost ceiling, exact region, and account-specific availability are still open. See the linked topology decision for official price sources and limits.
  - Added `gpu-control-db-migrate.service` as a manually started, hardened oneshot with no boot-install target. Production use remains gated on quiescence, paired backup/restore, and review of the exact release migration.
  - 2026-10-28 read-only Neon inventory found an existing unversioned v1 Gateway schema, zero runs/active slots, and existing local OAuth admin/session state. The initial isolated v1-to-v6 `Store.initialize()` rehearsal is historical; after schema v7, the current operator `--init-db` entrypoint was rerun twice against an isolated v1-shaped PostgreSQL 16 database and preserved synthetic run/OAuth rows, with unknown future schema rejected without mutation. This does not authorize or validate production migration; see `docs/acceptance/2026-10-28-neon-first-schema-migration.md`.
  - 現行Vercel Functions案は `gateway/vercel.json` の `maxDuration: 30` で、queueを常時監視するworkerには使わない。Vercel Sandboxは別製品で、現行公式資料ではPro/Enterpriseのsession上限が最大24時間、snapshotとDriveによる永続化がある。P3の構成選定時に候補比較はできるが、利用可能なplan、請求/上限、停止後の再開・queue監視、専用workerの信頼境界、DB/成果物の永続性を実環境で確認するまでは採用済みと扱わない。
  - Local Vercel package preflight builds a Gateway wheel from valid PEP 621 metadata, checks runtime dependencies, and CI performs a locked fresh-environment import. Preview build READY at `c1541a8` did not prove runtime imports: GET `/healthz` failed with `ModuleNotFoundError: gpu_control`. An explicit local uv source fixed this; preview `e67eb72` returned `/healthz` HTTP 200 with `configured=false`, verifying liveness/import only. The explicit include-outside-Root-Directory project setting was not directly read.
  - 比較対象は専用Linux host (systemd)、Vercel Sandbox + Drive、および必要なら既存のmanaged PostgreSQL/storage。選択理由、費用上限、failure/recovery実測を記録する。いずれもCPU policy enableより前に同じacceptance gateを通す。
- [x] ローカルOAuth/HTTP-auth契約を検証する: PKCE、redirect/client binding、同意とCSRF/origin、refresh rotation/revocation、scope enforcement、誤audience/issuer/subject/time、rate limit、owner/session境界。2026-10-28 current-worktree revalidation: `gateway/.venv/bin/python -m pytest -o addopts= gateway/tests/test_local_oauth.py gateway/tests/test_http_auth.py -q` — 35 passed, one existing Starlette deprecation warning. 詳細は`docs/IMPLEMENTATION_PROGRESS.md`。
- [ ] 実ChatGPT/OIDCでOAuth connect/refresh/revocationとworkspace action controlsを受入れ確認し、別owner境界を実環境で検証する。ローカル契約テストはこの受入れを代替しない。
  - 2026-10-28 offline regression fixed a rollback bug in the built-in OAuth failed-login counter; the fifth invalid password now activates a persisted lockout and expiry is verified. Live ChatGPT/OIDC and production owner isolation remain unverified. See `docs/IMPLEMENTATION_PROGRESS.md`.
- [x] 内蔵OAuthのissuer変更用オフライン移行手段を実装し、実DB複製とartifact fixtureでローカル検証した。移行元/先issuer・subjectの明示確認、quiescence、衝突・digest検査、再開可能なコピー/rollback手順、旧token/session失効、owner境界を検査する。実装とSIGKILL試験の範囲は`docs/acceptance/2026-10-28-owner-issuer-migration.md`を参照する。これはproduction migrationの承認や実行ではない。
  - Production rollout remains separate: stop all services/admission, take and verify a paired production backup, run read-only preflight, independently review the exact migration, apply it, then verify owner counts, artifact digests, old-issuer rejection, and cross-owner denial before resuming.
  - 移行元と移行先issuer/subjectを明示し、認証済みの同一ownerであることをoperatorが確認してから実行する。subだけの一致や新issuerへのログインだけでは移行を許可しない。
  - API、worker、supervisorを停止し、新しいsubmitを遮断した状態でDBとartifact volumeを同じ世代として退避する。通常のAPIリクエストや起動時migrationでownerを自動書換えしない。
  - runのowner、submission intent内のowner参照、artifact scope directoryをまとめて移行する。現行schemaに独立approval tableやplan内owner参照はない。owner/idempotency一意制約の衝突・対象件数・参照整合性を検査し、artifactを新scopeへコピーしてmanifestのsize/SHA-256を照合する。原本を保持し、DB更新とartifact切替の不一致から再実行・復旧できる段階設計にする。
  - 旧issuerのtoken/sessionを引き継がず、旧URLの認証を拒否する。移行後は新issuerでrun一覧、status、result、artifactの読出しを確認し、別ownerからの全経路が404/拒否となること、件数・owner境界・成果物digestが一致することを証拠に残す。
  - 実DB複製と実artifact fixtureで、成功移行、同一owner再実行、衝突時の無変更、途中失敗後の復旧、別owner拒否を検証する。通常運用への復帰は全検査成功後のみ許可する。
- [x] Paired DB/artifact backup generation and isolated restoreを実装・ローカルsynthetic PostgreSQL 16で実行し、run/OAuth stateとowner-scoped artifact retrievalを確認した。v7 refreshではOAuth `grant_id`/revocation状態も確認し、PostgreSQL 16 generationを別PostgreSQL 17.11 DBへrestoreしてschema/run/artifact/OAuthの保持を確認した。2026-10-28のcurrent-worktree full Gateway revalidationでもPostgreSQL 16＋digest-pinned CPU imageにより279件pass、2 optional skipsとなり、DB parallel admission、v4-v7 migration、lease fencing、DB outage recoveryを含む。手順と限界は`docs/acceptance/2026-10-28-paired-artifact-restore.md`、`docs/acceptance/2026-10-28-atomic-backup-generation.md`、`docs/acceptance/2026-10-28-local-integration-revalidation.md`に記録した。これはNeon固有挙動やtarget-host acceptanceを意味しない。
  - 2026-10-28 current-schema refresh: actual systemd in an isolated Ubuntu 24.04 container reported all seven backup-gated units `loaded/inactive`; the current worktree backup CLI created and verified a synthetic PostgreSQL 16 schema-v8 generation, then a separate PostgreSQL 16 target restored it with schema/run/active/cleanup state intact. The artifact archive was empty. This strengthens only local backup/restore evidence; no target host, Neon, production identity, artifact bytes, second operator, or RPO/RTO was accepted.
  - 2026-10-28 runbook consistency fix: the isolated restore example previously referenced detached `.sha256` sidecars that `backup_generation.py` never creates. Updated it to run `--verify-generation` against the published generation manifest, restore the actual `database.dump`/optional `artifacts.tar` names, and extract artifact bytes as the dedicated worker UID. This fixes documentation/tool contract drift only; second-operator and target-host recovery remain unaccepted.
  - 2026-10-28 stopped-service gate: the backup API requires `services_stopped_confirmed=True`, and the CLI requires `--confirm-services-stopped`. Before creating a generation it queries all seven local Gateway systemd units and requires `LoadState=loaded` plus `ActiveState=inactive`; new manifests record the operator attestation and per-unit states. Verification rejects explicit false or incomplete unit states while accepting legacy format-1 manifests with both fields absent. Unit-test systemctl outputs were stubbed; no target manager, backup, or restore was exercised for this follow-up. This local check cannot prove other hosts or manually started processes are stopped, so ingress/all-host shutdown remains required. Focused backup tests: 20 passed; full offline Gateway suite: 351 passed / 9 skipped. No production acceptance is implied.
  - 2026-10-28 backup procedure alignment: `docs/OPERATIONS.md` now explicitly stops the capacity timer/oneshot and manual bridge before backup, confirms the migration unit is inactive, and restores a previously active capacity timer only after the backup and artifact-mount check. This aligns the operator steps with the seven-unit local-state gate; documentation-only, no host command or backup was run.
  - 2026-10-28 capacity bridge concurrency: delivery pump invocations sharing the state path now serialize selection/send/acknowledgement under a dedicated advisory lock. A separate-process regression verifies exclusion and release; focused capacity event state module: 33 passed, one existing Starlette warning. This prevents simultaneous duplicate dispatch from local bridge processes but does not remove the crash-after-remote-acceptance retry window; a selected sender must support the cursor idempotency key. No sender or notification route is selected, and target-host delivery remains unaccepted.
  - [ ] Neon固有のpaired backup/restore挙動とsecond-operator手順を、承認済みの隔離環境で確認する。
  - [ ] 選定production database/artifact volumeでpaired backup/restoreを行い、second-operator手順とRPO/RTO実測を[`recovery drill record template`](../../acceptance/2026-10-28-recovery-drill-record-template.md)に記録する。計測境界と独立確認項目は用意済みだが、実ホストでのdrillは未実施。
- [x] `/readyz`はDB、schema migration version、worker/supervisor heartbeat、registry有効性を検証し、境界テストを持つ。コード上の実装証拠は`gateway/gpu_gateway/health.py`、`gateway/tests/test_health.py`、`gateway/tests/test_http_auth.py`。
  - [ ] 選定ホストに配置し、実サービス再起動・DB停止・stale heartbeat時にreadinessと回復動作を受け入れ確認する。
  - [x] `/readyz` とlocal CPU artifact storageのローカル契約を確認した。local_cpu workloadが有効な場合はartifact storage probeを必須とし、demo-onlyでは不要とする。probeはheadroom確認後に一時ファイルを作成・即unlinkし、開いたdescriptor経由でwrite/fsyncすることでread-only mountや実書込失敗をfail-closedに検出し、可視のprobe residueを避ける。`gateway/tests/test_artifact_storage.py` と `gateway/tests/test_http_auth.py` は38件pass。current-worktree Gateway全体はloopback-only PostgreSQL 16＋digest-pinned CPU imageで279 passed / 2 optional skips。PR review、実ホストmount/quota、deployed readiness確認は未完了。
- [x] Local CPU artifact admissionのfilesystem/headroom probeはcapabilities、prepare、worker直前でfail-closedし、systemd monitorも実装済み。ローカルfixture evidenceは`docs/acceptance/2026-10-28-artifact-storage.md`。
  - [ ] 選定ホストでfixed-size filesystem quota、alert通知/復旧通知、quota上限時のwrite失敗・cleanup、API/worker/supervisor継続稼働を実測する。`statvfs`だけをquotaや通知の証拠にしない。
  - 2026-10-28 continuation: Added host-independent alert bridge contract `docs/specs/capacity-alert-bridge-contract.md`. It fixes the journal allowlist, schema/state/cursor/replay rules, redaction, independent service identity, bounded delivery, and target-host acceptance without choosing a sink. Official SNS documentation confirms HTTPS endpoints require public reachability, subscription confirmation, and signature validation, so direct SNS HTTP delivery is not a drop-in fit for the current loopback Gateway. No bridge or sink was implemented/configured; provider/region/budget/origin/recipient/SLO remain open.
  - 2026-10-28 local implementation: `gateway/deploy/capacity_event_state.py` validates trusted `_SYSTEMD_UNIT` identity and bounded capacity events, allowlists fixed reason codes, persists cursor/status and each alert/clear transition atomically in a `0600` file, and retains a 64-record outbox with eight-attempt history. State mutations use a separate private `flock`; recent 256 opaque cursors are retained for deduplication, and event ordering never depends on realtime timestamps. `JournalctlSource` uses fixed no-shell arguments, selected JSON fields, unit/identifier filters, finite timeout and bounded batches. `JournalPoller` probes checkpoint retention before and after reads and raises unknown-state on a gap without advancing state. Polling with no checkpoint is refused; explicit bootstrap reads only the latest event and does not create a false clear on an initial `ok`. Fake-journal tests cover cursor resume, retention gap, baseline, trusted identity, concurrent writers, and clock rollback. `capacity_event_delivery.py` adds a bounded sink-agnostic pump, fixed notification projection, stable cursor idempotency key, and deterministic retry delay from 5 seconds up to 1 hour; sender exceptions are reduced to a fixed retryable result. `delivery_health()` exposes bounded state/attempt counters without event or cursor data. Fake-sender cases cover retry timing, acknowledgement, projection, exception redaction, and health output. Focused capacity tests: 27 passed; full Gateway suite: 332 passed / 9 skipped / one existing deprecation warning. No live Linux journal, timer/service scheduler, concrete sink, or notification acceptance is proved. Delivery is at-least-once across a crash after sink acceptance; use cursor as idempotency key where supported. No sink or target host was selected.
  - 2026-10-28 source-audit fix: added a separate process-wide `flock` across checkpoint read, journal queries, retention recheck, and complete batch/bootstrap application. Threaded overlapping-poller and separate-process lock regressions confirm poll serialization and lock behavior. Capacity-state/deploy-unit suites: 45 passed; full Gateway offline suite: 339 passed / 9 skipped; full Gateway Docker/PostgreSQL 16 integration suite: 345 passed / 2 optional skips. The exact lock also passed a network-isolated Linux-container subprocess probe using a pinned Python 3.12 image; no systemd service or live journal was exercised. A first tmpfs-backed DB attempt could not pass the recovery test after stop/start; the passing rerun used the pinned PostgreSQL image's anonymous data volume, and all test-created containers/volume were removed. Details: `docs/specs/capacity-alert-bridge-contract.md`, `docs/acceptance/2026-10-28-linux-capacity-poll-lock.md`, and `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
- [ ] `docs/CHATGPT_ACCEPTANCE.md`のSeven-day CPU operations observationに従い、接続切れ、worker再起動、停止、日をまたぐ検索を7日間記録する。現在はNOT STARTED。監視で実験を勝手に再実行しない。

  - 2026-10-28 manual bridge-poller slice: `capacity_event_bridge.py` requires explicit `--bootstrap-latest` or checkpointed `--poll-once` and emits only bounded state counters. Added a manual-only `gpu-control-capacity-bridge.service` with a distinct UID, private `StateDirectory`, `systemd-journal` read access, no network, and no application secrets/artifact/Docker authority; no timer was added while undelivered outbox entries have no selected sink. CI inventory and static deployment regression coverage include the new unit. Focused capacity/CLI/deploy-unit modules: 43 passed; Gateway suite: 334 passed / 9 skipped / one existing deprecation warning. The guarded helper passed systemd-analyze verify for all seven templates in cached Debian 12/systemd 252.39 with `--rm --network none` and a read-only repository mount. No service started; target-host runtime acceptance remains open. Membership in `systemd-journal` grants underlying host-journal read access; the runbook records this trust boundary. No host was changed.
  - 2026-10-28 retention-gap recovery follow-up: added explicit `--reconcile-latest` for an initialized checkpoint proven absent before and after reading one latest trusted event. The operator preserves pending outbox items and reannounces the latest retained status, even when unchanged; missing intermediate transitions stay unknown. The runbook includes the one-shot command and explicitly records that this is not host acceptance. Capacity state, backup generation, and systemd unit suites passed 71 tests, one existing Starlette deprecation warning. Independent review caught and corrected an unsupported `sudo -G` in the runbook; the corrected command uses the supplementary group configured for the bridge identity. Evidence: `docs/acceptance/2026-10-28-capacity-retention-reconciliation.md`.
  - 2026-10-28 operator-inspection follow-up: added `--show-health`, which reads only the private state file, never queries journald, and returns the fixed local outbox counter projection without cursors/event data. An independent review found the state read outside the CLI error boundary; moved it inside and verified corrupt-state failures return a fixed message without path/parse leakage. Focused capacity, backup, and deployment-unit suites: 73 passed, one existing Starlette deprecation warning. Evidence: `docs/acceptance/2026-10-28-capacity-bridge-health-cli.md`. It does not report journal-reader health or prove notification receipt.

### 2026-10-28 continuation revalidation

- PR #51 was rechecked read-only through GitHub: still OPEN/DRAFT at pushed
  head `f054aebe96460fe033dde8d91d7e3bbab0255655`, no reviews, remote checks
  successful. Uncommitted worktree changes are outside those checks.
- Current local Gateway suite with digest-pinned CPU image and disposable
  PostgreSQL 16: **342 passed, 2 optional skips** (Torch and Modal SDK).
  Fixed loopback port `55543` was required after a dynamic-port attempt lost
  reconnection when PostgreSQL was restarted during recovery testing. The
  uniquely named database container was removed by an exit trap. Root suite:
  **536 passed, 1 skipped**. P3 capacity/deploy focused tests: **51 passed**;
  seven systemd templates pass the isolated Debian 12/systemd 252.39 verifier.
- Official Modal docs were refreshed: egress is billable since 2026-10-01 and
  billing SDK summary/report/rates expose usage or charges; they still do not
  provide remaining eligible credits by component, quota headroom, or a
  per-run stop guarantee. This does not close the quota evidence gate.
- Remaining P3/P1 gates depend on selected-host, origin, region, budget,
  recipient/SLO, authorized deployment, and intended ChatGPT workspace access.
  Until those are explicitly set and accepted, continue local tests/specs only;
  no provider, host, production, or paid state is enabled. P4 provider-evidence
  ingestion and lifecycle wiring remain behind ChatGPT CPU acceptance.

目標: 通常負荷でstatus応答p95 2秒以内、submit応答5秒以内、local cancelから解放30秒以内。環境・サンプル数・負荷条件を証拠に含め、未測定をPASSにしない。DB backupは当初RPO 24時間/RTO 2時間を目標とし、受理済みjob自体はDB commit後にのみ応答する。

完了条件: ownerが日常利用でき、再起動/バックアップ復元手順を別担当者が再現できる。CPU版としてリリース可能。有償GPU完成を待たせない。

## P4: 最小コストの資源選択と実GPU（3〜6 PR）

主な変更先: 新規 `capabilities.py`, `selection.py`, `costs.py`, `workloads.py`、既存Modal backend、対応tests/docs。

Implementation brief: [`docs/specs/p4-capability-selection-contract.md`](../../specs/p4-capability-selection-contract.md)。既存`PricingVerificationResult`と`ApprovedExecutionPlan`の境界を維持し、discovery/selectionでhuman authorizationやprovider submitを発生させない。

- [x] provider単位ではなくworkload実行可能性を判定する。GPU/VRAM、OS/architecture、runtime依存、timeout、任意の待ち時間上限、結果回収、cleanup、費用証拠の有効期限を入力にする。2026-10-28 offline follow-up adds operator-declared runtime requirements and queue-wait ceilings to the workload fingerprint; candidate evidence must declare supported runtimes and a current wait estimate or is rejected. This closes the offline contract only, not real provider inventory.
  - 2026-10-28 offline implementation: `src/gpu_control/workloads.py`, `capabilities.py`, `selection.py` define immutable workload requirements, independent availability/cost evidence, per-run cost components, freshness checks, deterministic compatibility filtering, `FREE_FIRST`, and refusal reasons. Gateway now accepts explicit optional P4 requirements in its operator manifest and invokes the selector read-only; absent provider inventory fails closed as `PROVIDER_EVIDENCE_UNAVAILABLE`. Local root/Gateway suites: 517/262 passed (1/8 skipped); Docker API/worker image builds and shared-package imports passed. The GPU example declares execution requirements but leaves exact source repository/SHA blank, with regression coverage that selection remains blocked until they are supplied. No provider/account/live GPU evidence is implied; Vercel deployment packaging remains unverified. Details: `docs/specs/p4-capability-selection-contract.md`.
  - 2026-10-28 provider-source correction: the repository already contains a fixed-origin RunPod GraphQL collector for GPU type, VRAM, secure price, and exact-datacenter stock, with reviewed contract pin, content digest, and a maximum 300-second TTL (`src/gpu_control/providers/runpod_current_pricing.py`). It is not wired to Gateway selection and does not cover runtime/OS, queue wait, result transport, cancellation/cleanup, quota, or full run cost. Therefore replace “no provider evidence source” with “no complete, Gateway-ingested capability evidence.” Reassess the Modal-first sequence before implementing an adapter; keep all unobserved fields unknown. No credentials or live provider request were used.
- [x] `LOCAL / FREE / FREE_QUOTA / CREDIT_BACKED / PAID / MANUAL_ONLY / UNSUPPORTED / UNKNOWN`を公開し、availabilityと費用分類を別々に保持する。2026-10-28 Gateway capabilities now emits `provider_availability` (`AVAILABLE` / `UNAVAILABLE` / `UNKNOWN`) independently from its submission-state `availability` and `cost_classification`; configured GPU providers remain `UNKNOWN` until live provider evidence exists. All 23 `gateway/tests/test_experiment_api.py` tests passed.
- [ ] まず既存Modal adapterの公式APIを再検証し、利用者アカウントの実際のquota/credit/支払い制御を確認する。実行可能性がなければ理由を記録して他候補1つを調査する。
  - 2026-10-28: Modal Sandboxの公式timeout/idle-timeout/termination仕様と公開pricingを現行adapterと照合した。worker専用adapterは固定argv・prebuilt image・GPU/CPU/RAM/runtime・block_network・cancel/reconcileの境界を持つが、ユーザーworkspaceのplan/quota/credits/budget/overageは未確認。公開価格のincluded creditはzero-additional-cost保証ではない。Modal readiness記録: `docs/decisions/2026-10-28-p4-modal-readiness.md`。このP4 itemはアカウント確認が残るため未完了。
  - 2026-10-28 update: Modal公式Budgets docsはWorkspace budget（credits適用前usage cap）とnet spend limit（out-of-pocket cap）を分離し、spend limit到達後もcredit-covered workloadはusage limitまで継続し得ると説明している。ゼロのnet spend limitだけではrun完了に足りるcredit残高も、storage/egressを含む全費用の補填も証明しない。現coreにはcredit残高と適用対象componentの期限付き証拠がないため、P4にモデル化・submit前/worker直前再評価を追加した。アカウント値はworkspace ownerによるread-only確認が必要。
  - 2026-10-28 official SDK check: `Workspace.billing.rates()`, `report()`, and `summary()` expose rate and observed-usage evidence; `summary()` documents metered/billed costs, adjustments, and cost breakdown. The `Workspace.settings.list()` reference does not define documented fields for remaining usage/eligible credit, configured budget/net-spend caps, or stop-on-overage. Billing APIs alone cannot supply complete `QuotaEvidence`; do not infer quota from public plan credit or billing totals. See the Modal readiness decision.
  - 2026-10-31 provider-lane correction: Modal remains the candidate-bound adapter target and RunPod remains under P5, but there is no executable Modal credit-backed lane yet. The registry/worker now give `CREDIT_BACKED` a distinct opt-in and `validate_credit_authorization` hook. A pure offline signed credit-use verifier and default-empty issuer/key settings now bind gross credit debit, zero out-of-pocket ceiling, quota fingerprint/coverage, owner/actor and exact plan. They are not wired to admission and no provider implements the hook. Do not treat account credits as consent. RunPod's signed observation is catalog stock/accelerator pricing only; the official Pod guide documents retained volume charges after stopping, and its existing core adapter requires `LiveExecutionPermit`. Keep provider registration disabled pending durable authority integration, live quota evidence, independent review, and actual-device/release acceptance. See `docs/decisions/2026-10-28-p4-modal-readiness.md`. No provider/account call or allocation was made.
  - 2026-10-28 offline adapter: `gateway/gpu_gateway/modal_evidence.py` now collects only injected-workspace `billing.rates()` and `billing.summary()` data, with strict normalization, timestamp/cycle checks, and a stable fingerprint. It labels the result `billing_only`, marks quota evidence unavailable, and is not eligible for selection. Twelve fake-workspace unit cases passed; no SDK/account call or credential access occurred. This does not close provider-evidence or revalidation items. The Gateway offline suite passed 301 tests with 9 skips (optional Torch, prebuilt image, Modal SDK, and PostgreSQL integrations unavailable/configured out); this is not live provider or product acceptance.
  - Implemented offline core slice: `QuotaEvidence` binds remaining usage headroom, eligible credit balance/components, source reference, observation time, and expiry into `CapabilityEvidence` fingerprints. A zero-additional-cost `CREDIT_BACKED` candidate is selectable only when all gross costs are known and covered by current credits, available usage headroom is sufficient, and an enforced stop-on-overage hard cap is present. Insufficient/stale quota returns `QUOTA_UNKNOWN`; uncovered egress/storage and unknown/chargeable overage are rejected. Core `revalidate_approved_candidate` binds approved workload/provider/resource/evidence fingerprints and returns `APPROVED_PLAN_STALE` on changes or expiry without provider substitution. No Modal account or live call was used.
  - 2026-10-28 continuation: Gateway `PlanV2` has a strict optional `selection_binding` for exact workload/provider/resource/evidence fingerprints; presence changes the approval fingerprint, unknown fields and provider mismatch are rejected, and absent-field serialization preserves existing schema-v2 fingerprints. Candidate-bound plans are rejected by local CPU admission because that path does not perform P4 evidence revalidation. Integration with selection and provider-evidence revalidation is complete as described in the integration follow-up below. No Modal account or live call was used.
  - 2026-10-28 integration follow-up supersedes the earlier “not connected” status: added an idle-worker-only RunPod GraphQL collector, verified-snapshot conversion, GPU prepare-to-PlanV2 binding, transactional submit revalidation, and worker pre-intent revalidation. Changed or expired evidence fails without resource substitution. Full Gateway suite: 370 passed / 9 skipped; root suite: 540 passed / 1 skipped. Modal and RunPod registrations still have `supports_candidate_binding=false` because no PlanV2-compatible execution/result/cleanup backend has passed acceptance; no plan can queue. No provider credential/API/GPU use occurred.
  - 2026-10-28 prepare retry correction: an exact retry now resolves the owner-scoped existing run before rechecking volatile candidate evidence, so expiry or inventory changes cannot create a replacement run or reject a transport retry. New runs store a stable hash of the user request; existing PlanV2 rows with the former selected-plan hash are recognized by their immutable request fields. A changed request under the same key still conflicts. Candidate API/local-admission modules: 53 passed; full offline Gateway suite: 388 passed / 9 skipped (Torch, Modal SDK, container image and PostgreSQL integrations unavailable). No provider call or allocation occurred.
- [x] FREE_FIRSTは適合候補を絞り、証明済みの追加料金0枠を優先する。credit残高だけでゼロ課金を保証しない。overageを確実に止められない枠は0ドル要求でBLOCKEDにする。Evidence: core selector regression tests and current-Gateway capabilities response; live provider evidence remains unavailable.
- [x] 完全な候補在庫でGPU候補がない場合は `FREE_GPU_UNAVAILABLE`、quota不明は `QUOTA_UNKNOWN` を返す。未確認の実provider在庫は `PROVIDER_EVIDENCE_UNAVAILABLE` のままにし、capabilitiesにlocal CPU候補と未受入のpaid GPU経路を分けて表示する。実アカウント、GPU実行、paid prepare受入は未完了。
- [ ] GPU smokeは実デバイス情報と小さいCUDA演算を含め、device名、VRAM、provider handleに対応する証拠、exit、時間、使用量、cleanupを記録する。
- [x] quotaの競合消費・見積り失効をsubmit/worker直前に再評価し、planを勝手に別providerへ変更しない。submit transactionとworker submission intent直前で同じ候補の最新署名済み証拠を確認する。provider accountの実quota取得とGPU実行は未受入。

P4 Gateway wiring order (2026-10-28): (1) a default-off, idle-normal-worker-only bounded RunPod GraphQL collector now publishes signed 120-second observations from exact operator GPU/datacenter mappings; fake-client coverage only, no live provider call; (2) schema-v8 `gateway_provider_observations_v1` stores signed envelopes and monotonic versions; API and worker verify them using the pinned key; (3) API strictly converts candidates and calls the selector; (4) a selected candidate is bound to PlanV2 and revalidated before prepare persistence, under the submit transaction, and immediately before worker submission intent. No provider registration yet declares `supports_candidate_binding`, so candidate-bound plans cannot queue or reach an execution backend. Still missing: full capability/cost/quota evidence, PlanV2-compatible GPU execution and trusted device/result/cleanup evidence, live GPU acceptance, and separately authorized paid execution. RunPod `HIGH` stock is an offer signal, not a reservation, and its catalog price is not all-in cost. See `docs/specs/p4-capability-selection-contract.md`.

### P4 implementation boundary and next sequence (2026-10-28)

Offline candidate selection is wired end to end through signed provider
observation verification, strict candidate decoding, compatibility selection,
exact-resource PlanV2 binding, and revalidation before prepare persistence,
inside submit's transaction, and before worker submission intent. It is still
not an executable GPU product: RunPod and Modal registrations both leave
`supports_candidate_binding=false`; no registered backend consumes the exact
PlanV2 resource and implements authenticated observation, result transport,
and independently verified cleanup. Account quota, complete per-run costs,
real device output, live cancellation, and resource absence are unverified.
Keep provider switches off and `policies/repository-state.yaml` parked.

2026-10-30 continuation: added a pure Ed25519 signer for `gateway_adapter`
candidate receipts. It binds the PlanV2 fingerprint, source/image/resource,
run ID, normalized result digest, and a bounded provider-object projection;
the output is checked by the existing receipt verifier before return. This is
only the receipt construction primitive: it neither authenticates the supplied
provider projection nor implements a provider adapter, and no registration or
provider switch was changed. Strict recursive JSON validation rejects numeric
keys, tuples, cycles, non-JSON values, and overlong data. Focused tests passed
20/20; full Gateway passed 442/2 skipped, and independent code review found no
remaining issue in this primitive. See
`docs/superpowers/plans/2026-10-31-p4-adapter-receipt-signer.md`.

2026-10-31 code-boundary ruling: the existing core
`src/gpu_control/providers/runpod_adapter.py::RunPodV2Adapter` requires a
validated `LiveExecutionPermit` at construction and before provider operations.
That adapter belongs behind the P5 paid-authorization path; do not reuse it as
the P4 free/credit-backed candidate backend or convert the offline paid-envelope
verifier into that permit. P4 needs a separate Gateway candidate adapter that
consumes the exact `PlanV2.selection_binding`, proves current cost/quota evidence
at submit and immediately before create, never substitutes the selected
resource, and implements candidate receipt/result retrieval, cancellation,
reconciliation, and cleanup. Registration remains disabled until account
evidence and independent acceptance establish the actual execution lane.
The registry now sends `CREDIT_BACKED` to a distinct credit-authority hook,
while the P5 verifier accepts only `PAID`; no current backend implements the
credit hook, so the Modal credit-backed route remains non-executable. Until a
signed credit-consumption authority is implemented and reviewed, only truly
`FREE`/`FREE_QUOTA` zero-additional-cost candidates can use P4 without P5
authorization.
Cost if wrong: a genuinely zero-cost lane could be delayed; reusing the paid
adapter without its validated permit could instead allow spend outside P5.

Next work, in dependency order:

1. Complete real ChatGPT CPU acceptance and P3 target-host/restore/operations
   acceptance. Offline MCP and systemd checks do not satisfy these product
   gates.
2. Select one GPU provider after owner-authorized, read-only account review.
   Record plan, region, quota, budget/spend limits, stop-on-overage behavior,
   and all-in CPU/GPU/storage/egress evidence with provenance and expiry. If
   complete zero-additional-cost evidence is unavailable, leave the free-GPU
   route blocked.
3. Implement one exact-candidate backend: consume the approved PlanV2 without
   substitution; reconcile ambiguous create without automatic retry; bind
   authenticated execution/device/result evidence to the plan; retrieve and
   digest-check results; cancel and independently verify cleanup.
4. Add fake-provider lifecycle regressions for create ambiguity, worker crash,
   cancellation, resource substitution, expired/invalid receipt, result
   tampering, and cleanup uncertainty. Keep registration opt-in false through
   independent source/security review and live evidence collection.
5. Only after account, security, cost/quota, and authorization gates pass, run
   a bounded free-GPU canary under separately approved scope. Record GPU/device,
   plan/run identity, result digest, realized cost, and cleanup as separate
   evidence claims.
6. P5 paid execution remains separate: design and verify an independently
   issued run-specific spending authorization mapped to the existing RunPod
   permit. Browser approval and a positive estimate ceiling are not spending
   authority. This roadmap authorizes no paid call.

2026-10-28 current-worktree integration revalidation after OAuth atomicity and
provider wiring: Gateway suite passed **403/2 optional skips** with PostgreSQL
16 and digest-pinned real local CPU containers; root/core suite passed **549/1
optional skip** after quoting the RunPod retirement date so YAML consumers get
an ISO string. Full scope and harness correction are in
`docs/acceptance/2026-10-28-local-integration-revalidation.md` and
`docs/IMPLEMENTATION_PROGRESS.md`. This does not change provider registrations,
which remain ineligible for candidate-bound execution, or the parked policy.

候補扱い: local CUDA/ROCmは実ハードウェアがある場合のみ。MacのMetal/MPSはCUDA成功として扱わない。Kaggle、Hugging Face/ZeroGPU、user-operated Colab、GitHub Actions CPUは公式の実行・回収・停止APIと規約を検証してから採用。現時点で無料・無人運用可能とは認定しない。

完了条件: 最低1つの実GPU backendでGPU実測、復旧、cancel、費用/cleanupが確認済み。無料条件が成立しなければFREE_GPU_EXECUTIONはBLOCKEDのままCPU版を維持する。

## P5: RunPodの有償実行（3〜5 PR）

主な変更先: `src/gpu_control/human_authorization.py`, `providers/`、新規Gateway core bridge、activation docs/policies。

- [ ] PR #43由来のallocation直前期限再確認、HTTP境界、receiptに結びついたrecovery-onlyを現行main上で検証する。
  - Offline hardening added: RunPod REST v1/v2, pricing GraphQL, and S3 reads now reject redirects and cap response bodies. Both adapters revalidate the live permit, exact price evidence freshness, and pre-create occupancy at one timestamp immediately before the create call. Injected-clock tests prove expired evidence prevents allocation; this does not verify live provider compatibility or the remaining receipt/recovery-only behavior.
- [ ] Gateway–RunPod permit bridgeを実装する。現行permitはGitHub protected workflow/Environment由来のunsigned dataclassで、Gatewayはbrowser approvalしか永続化していない。ChatGPT実行向けの独立paid-authority issuer、run固有署名envelope、PlanV2からApprovedExecutionPlanへのexact mapping、durable storage、pre-intent/pre-create再検証、失効/recoveryを先に設計・脅威レビューする。詳細は `docs/specs/p5-gateway-runpod-permit-bridge.md`。ブラウザ承認からcore evidenceを合成せず、受入れまでprovider paid flagsはOFF。
- [ ] 保護main、必須checks、必要なEnvironment/権限、immutable image、現在の価格/在庫、Network Volume/S3 transportを確認する。
- [ ] 同一アカウントの並行submitを安全に直列化する。現行RunPod adapterの前後occupancy snapshotはmutexではなく、worker death・曖昧create・inventory遅延後にleaseを安全に解放する機構もない。`docs/specs/p5-gateway-runpod-permit-bridge.md`のP5.3aに従ってaccount-scope HMACとDB永続leaseを実装し、confirmed cleanupまで占有を保持する。別process/connection、曖昧create、回復、cleanup commit境界をoffline競合試験し、その後にのみ別途承認されたcompetition canaryで重複allocationが0件である証拠を得る。
- [ ] GPU時間だけでなくCPU/RAM、storage、egress、cleanup遅延、失敗時コストを含む見積りを出す。未確定料金はnull/unknownにし、要求上限とproviderが強制できる上限を区別する。
- [ ] authority、支払上限、期限、最大同時数、停止条件を具体化した最小canaryを人間承認後に実行する。
- [ ] 別経路のprovider観測で資源解放を確認する。永続Volumeの保持課金を明示し、Pod解放だけで全費用終了と言わない。

完了条件: 実ChatGPTからexact paid plan承認→submit→result/cancelが成立し、請求・cleanup証拠が揃う。既存ゲートを外すだけで完成にしない。

## P6: 実際の研究・開発に役立つ実験（3〜6 PR）

- [ ] `orbitune-train-small`など登録済み学習を追加。source SHA、image digest、dataset版、seed、ライブラリ、device、パラメータをmanifestに保存する。
- [ ] 「もう一度」「前の実験との比較」を新runとparent_run_idで表現し、通信再送と区別する。
- [ ] A/B比較は双方のexact source・設定・device・測定条件を記録し、測定差と意味的な品質差を混同しない。
- [ ] JSON result schemaをworkloadごとに定義し、欠損metricsや実行失敗を成功サマリーに変換しない。
- [ ] 検索にworkload、repository、SHA、状態、期間を追加。曖昧な「昨日の実験」で複数候補があるなら一覧を返す。
- [ ] operator向けworkload登録手順を整備。未知のrepo/SHAは `WORKLOAD_NOT_REGISTERED` と登録方法を返す。自然言語だけで未審査コードを実行可能にはしない。

完了条件: 別会話から実験を再発見し、再実験と比較が再現可能な証拠付きで成立する。

## P7: 継続保守と必要に応じた拡張

- [ ] 月単位でdependency/MCP/provider仕様を点検し、更新PRと互換性試験を用意する。
- [ ] backup復元・強制停止訓練、artifact保持期限、quota、固定費、未解放資源を定期確認する。自動監視の作成は別途ユーザー指示で行う。
- [ ] providerは利用実績から必要なものを1つずつ追加する。共通contract試験と実canary受入を必須にする。
- [ ] multi-user、private repositories、大きなcheckpoint、任意実験は個別設計・脅威モデル・運用予算を持つ後続milestoneにする。
- [ ] 実行完了のpush通知は必要性とChatGPT側機能を確認して別途設計する。初期版はユーザーのstatus/result照会で完結する。

## リリース判定と証拠

`docs/RELEASE_MATRIX.md`に以下を独立してPASS / FAIL / BLOCKED / UNCERTAINで管理する。

| 判定軸 | PASSに必要な実証 |
|---|---|
| MCP_CONNECTIVITY | 実ChatGPTのOAuthとtool discovery/call |
| CHATGPT_TOOL_USABILITY | 会話だけでprepare/submit/status/result、別会話から検索 |
| CPU_EXECUTION | mockを使わない実containerのprocess exit・metrics |
| FREE_GPU_EXECUTION | 実GPU + 正当な追加料金0枠 + 利用量/cleanup |
| PAID_GPU_EXECUTION | exact paid authorization + 実GPU + 費用/cleanup |
| RECOVERY | 実worker停止を挟む同一run復旧、二重作成なし |
| CANCELLATION | 新規実行OFFでも停止し、実資源解放を確認 |
| RESULT_RETRIEVAL | owner一致、別会話、source/plan/artifactの対応 |
| SECURITY | 定義した認証・隔離・入力・権限試験とレビューの完了。完全安全の保証ではない |

各記録: 日時、control-plane SHA、workload SHA、image、run_id、fingerprint、環境、実施者、入力/観測、失敗内容、cleanup、既知費用、不明点、証拠path。秘密値は保存しない。期限切れCI artifactリンクだけに依存せず、公開可能なreceiptを長期保存する。

## 設計上の責務

Gatewayは認証・plan・承認・queue受付・結果公開を担う。workerは信頼済みplanから実行し、provider秘密を保持する。provider backendはstart/inspect/cancel/reconcileを担当する。workloadのstdoutはデータであり、owner・費用・GPU使用・cleanup証明を上書きできない。

planを変更する場合は新fingerprint・再承認とする。queued jobに対するregistryや設定変更もworker直前に検証し、元planから別資源へ自動移行しない。低リスク許可もpolicy versionと失効条件を持つ。

## 参照

- [調査基準main](https://github.com/Unjuno/gpu-control/tree/24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e)
- [監査PR #43](https://github.com/Unjuno/gpu-control/pull/43)
- [既存CPU実装](https://github.com/Unjuno/gpu-control/tree/24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e/gateway/project_control)
- [ChatGPTのcustom MCP接続](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
- [OpenAIの認証仕様](https://developers.openai.com/plugins/build/auth)

接続機能・プラン・UI・OAuth要件は変わり得るため、P0と実接続直前に公式資料と利用アカウントで再確認する。自作HTTPクライアントの成功をChatGPT接続PASSの代用にしない。

## 2026-10-28 P4 execution-receipt continuation

The Gateway now has an offline Ed25519 candidate execution receipt verifier and
a separate `GATEWAY_CANDIDATE_RECEIPT_PUBLIC_KEYS_JSON` trust set. A successful
candidate GPU result must bind its exact selected resource, run ID, approved
PlanV2 fingerprint, source/image identity, provider execution ID, device
identity/model, and normalized result digest. The worker also requires an
adapter to reconcile its authenticated live provider object and lifecycle.
Contract: `docs/specs/p4-candidate-execution-receipt-contract.md`.

This is only a verifier/interface. No provider API or account has been shown to
emit or authenticate this receipt, and no key provenance/rotation, GPU run,
result collection, cost, cancellation, or cleanup acceptance has passed. Thus
P4 still has no accepted runnable GPU backend; keep all provider switches off,
registration opt-ins false, and `policies/repository-state.yaml` parked. The
next code action is to verify current primary provider API capabilities for
execution identity, assigned device and result retrieval; implement one
provider-specific adapter only when its authenticated evidence can satisfy the
receipt and cleanup contracts. The remaining P1 ChatGPT acceptance, P3 host
acceptance, live GPU gate, and separately authorized P5 paid path are unchanged.

2026-10-28 receipt trust-mode update: P4 receipt verification now explicitly
supports two signer scopes: provider-signed receipts and separately namespaced
trusted-adapter attestations over authenticated provider API snapshots. The
receipt stores signer scope and evidence-source/provider-object digest; adapter
attestation is not provider hardware signature. Focused receipt tests (9), the
full Gateway suite, and the full root suite pass. This remains offline contract
evidence only. No provider key provenance, adapter key, provider backend, live
GPU, cost, or cleanup acceptance exists. Preserve parked mode and all provider
flags. Next verify provider result transport, authenticated object identity,
cancellation, uncertain-create reconciliation, all-in cost and cleanup gates;
then build at most one disabled-by-default adapter using the evidence mode its
provider actually supports.

2026-10-28 candidate result read verification: Successful candidate GPU results
now have their signature, key scope, plan/run/resource/image/source binding,
ResultV2 claims, and normalized result digest rechecked on API reads. Historical
reads accept expired receipts only after verifying the original bounded
validity window and signature. Tampered stored candidate success is returned as
`failed/result_integrity_failed` with result redacted; artifact retrieval uses
that verified response. Focused tests (11), full Gateway, and root suites pass.
This remains offline security-contract evidence; no live provider/GPU or
ChatGPT retrieval is accepted. Next provider implementation must provide the
provider-signature or adapter-attested API evidence scope already defined, plus
live reconciliation/cost/cleanup gates. Keep parked mode and paid gates.

2026-10-28 candidate cleanup result invariant: Successful candidate GPU
`ResultV2` now requires `cleanup_state=complete`, including on persisted API
reads. Mutated metrics or cleanup state are returned as integrity failure with
result redacted. Focused candidate/read/contract checks (29), full Gateway, and
root suites pass. This is not independent provider cleanup attestation or live
resource absence proof. Keep live GPU and paid execution unaccepted; mode stays
parked.

2026-10-28 P5 gateway paid gate: Candidate-bound P4 support is now separate
from `supports_paid_execution`. Nonzero/unknown/non-free cost evidence requires
the paid flag; Gateway submit rejects it before queue/slot reservation when the
flag is false. The worker requires a trusted run-specific paid permit validator
before submission intent and provider call. This does not itself verify a
`LiveExecutionPermit` or connect the existing RunPod core adapter. Focused
registry/API/recovery tests (39), full Gateway and root suites pass. No paid
permit, credentials, provider call, GPU, billing, or host change. Next bridge
the exact approved Gateway plan to the existing core paid permit and fresh
pricing/occupancy/result-transport evidence, keeping all opt-ins off until
independent acceptance. Parked mode remains.

P5 permit integration regression follow-up: Worker coverage now proves a PAID
candidate with a rejected run-specific permit creates no submission intent or
provider resource and releases its slot. Remote-provider zero-cost claims are
restricted to FREE/FREE_QUOTA with exact zero additional cost; LOCAL is limited
to local providers. Full Gateway and root suites pass. This does not integrate
or validate the existing RunPod core permit in the Gateway. That exact-plan
bridge remains next, with all provider flags and parked policy unchanged.

## 2026-10-28 P4 RunPod API source revalidation

## 2026-10-28 Current-worktree security review

Codex Security scan `f9f8d84d-05bd-40d6-a241-d2856e841475` completed against
the current worktree snapshot at base/head
`f054aebe96460fe033dde8d91d7e3bbab0255655`, digest
`codex-security-snapshot/v1:sha256:d706e1d36e6e99c8408c5bd474fca42dbb7b9236d27f1304453c5408d02f82f7`.
All 37 compact changed-source inventory rows were reviewed; there were 0
candidate findings and coverage is complete for that source-level diff review.
Documentation and tests were excluded; no runtime, deploy, credentials, live
provider calls, GPU or paid resources were used. This does not change the
separate GitHub review, host, ChatGPT or provider acceptance gates. Full scope
and report path are recorded in `docs/RELEASE_MATRIX.md`.

Official RunPod docs now announce REST v1 retirement for 2026-11-15. The repo
contains a current REST v2 client plus a separate deprecated REST v1 client and
adapter. Official v2 docs expose authenticated Pod/GPU identity, runtime and
CUDA fields, lifecycle states, log streaming, and terminate. Record:
`docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`.

Ruling: future live RunPod work must use the v2 client and must not activate the
v1 adapter — the retirement date makes v1 a short-lived dependency, and the
current v2 API documents the lifecycle and identity surface needed for
reconciliation. The cost if this ruling is wrong is migration work if the v2
API's live behavior or account permissions do not match the docs; no live
provider request is authorized by this ruling. Before any registration opt-in,
validate v2 against a provider account under a separate bounded authorization,
then prove the authenticated result transport, post-run object reconciliation,
independent adapter signing key, cleanup, and cost/quota requirements. All
provider registrations remain disabled; mode remains parked.

## Active-goal continuation refresh — 2026-10-31 03:38 JST

- Current checkout is `codex/chatgpt-cpu-vertical` at
  `a794438f42bd7246f463eaaa40d963af0aae9d13`; it is 68 commits ahead of local
  `origin/main` and 2 commits ahead of the pushed PR #51 branch, with 40
  modified/untracked paths. PR #51 remains OPEN/DRAFT at
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, no GitHub review/comments, and
  seven required Actions checks passing on that remote head only. Current local
  changes remain outside those checks.
- The selected Security Review was completed on the current uncommitted diff
  with no actionable findings. This is separate from GitHub review. The current
  local full-suite evidence is Gateway **480 / 2 optional skips** and Core
  **550 / 1 Python-version skip**. Focused current-source PostgreSQL evidence
  also passed backup-manifest integrity **1/1** and OAuth/migration **7/7**;
  local OAuth/migration tests passed **17/17**. See
  `docs/IMPLEMENTATION_PROGRESS.md` and the linked acceptance records.
- The available ChatGPT browser is logged out. Production `/healthz` and OAuth
  metadata respond, but `/readyz` is 404 and unauthenticated `/mcp` is 401. The
  protected PR preview redirects to Vercel SSO. No ChatGPT authorization or
  tool call has run. This keeps P0 workspace eligibility and P1 product
  acceptance open; the remaining worktree-safe path is review preparation and
  scoped local validation until authorized workspace/endpoint access exists.
- P2 local CPU recovery is implemented and locally exercised. P3 target-host
  install/restore, seven-day operation, notification delivery, and measured
  RPO/RTO remain open; host, region, cost ceiling, public origin, alert route,
  and SLO need an owner decision before external setup. P4 lacks an accepted
  live GPU backend. P5 remains an offline authorization verifier without an
  issuer, persistence, worker wiring, or provider call. Keep all provider
  switches disabled and `policies/repository-state.yaml` at `mode: parked`.

This dated refresh supersedes earlier “current” snapshots in this plan. It
does not authorize a push, merge, deployment, host purchase/provisioning,
production migration, provider call, policy activation, or paid allocation.

2026-10-31 03:41 JST P2 verification delta: reran the current-source
worker-crash-after-real-container-start integration with the current CPU image
and isolated PostgreSQL 16; **1 passed**. The supervisor recovered the same
run/result, confirmed artifact and cleanup, removed the run resource, and
released the slot. The dedicated DB container was removed. This adds local
current-source evidence only; target-host, worker-host-loss, and ChatGPT
recovery remain unaccepted. See
`docs/acceptance/2026-10-31-postgres-container-crash-recovery.md`.

### 2026-10-31 continuation delta — current local and external state

- Re-ran the current working-tree Gateway suite with the pinned CPU image and
  a disposable loopback-only PostgreSQL 16 container: **480 passed, 2 optional
  skips**. Core: **550 passed, 1 Python-version skip**. The container was
  removed. Details: `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`.
- The latest working-tree Security Review found zero reportable candidates in
  five changed runtime-source files. It was a sequential review and did not
  cover tests, docs, external runtime, or ChatGPT. Its report and limitations
  are recorded in `docs/IMPLEMENTATION_PROGRESS.md`.
- P0 branch protection was re-read: `main` requires one approval, strict
  required checks, stale-review dismissal, conversation resolution, and admin
  enforcement; force pushes and deletion are disabled. PR #51 remains
  OPEN/DRAFT at remote head `aa681f4062dac6b73bcf380a38a4258b96a47e1`, with
  all seven checks passing but no submitted review. The 41-path working tree
  is outside those remote checks; the count includes the new acceptance
  record added after that readback.
- Production still serves old `main` SHA
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; public `/readyz` returns 404.
  The PR preview is READY but SSO-protected. The current ChatGPT browser is
  logged out, and Vercel environment-variable listing is denied. No share
  link, GitHub write, deployment, provider call, or account setting was
  changed. P1 ChatGPT acceptance remains NOT RUN.
- P2 local recovery and P3 local paired-backup evidence are stronger, but
  target-host operations and measured recovery objectives remain open. P4 has
  no accepted live GPU execution. P5 signed paid authorization is not wired
  into worker admission and one-use replay control is absent. Keep
  `policies/repository-state.yaml` at `mode: parked` and preserve the full
  objective.
