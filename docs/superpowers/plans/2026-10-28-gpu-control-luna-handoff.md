# Lunaへの実装引き継ぎ

## 継続ゴールと現在地（2026-10-28、PR state・運用差分再確認）

最終ゴールは、ChatGPTの通常会話だけで登録済み実験のprepare/submit/status/result/search/cancelを行い、同じjobの実行・復旧・成果物を正確に返すこと。長期ロードマップの順にP3運用、P4実GPU、明示承認付きP5有償、P6再現可能な研究実験、P7保守へ進む。実装計画の現行スナップショットと次の順序は `2026-10-28-gpu-control-roadmap.md` を参照。

## 最新状態 — 2026-10-30

- 作業ブランチ `codex/chatgpt-cpu-vertical` は `b3c355404815f1bb8ce711fe1e8db05b6f9ba2e5`、worktreeはclean。PR #51は `main` (`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`) 向けにOPEN/DRAFTで `REVIEW_REQUIRED`。最新必須CIは全件success。Gateway CIのPostgreSQL + digest-pinned local CPU lifecycleは424 passed / 1 skipped、root suiteは550 passed / 1 skipped。PRにGitHub reviewはまだない。
- PR preview deployment `dpl_5Lb4vGMSD9PsKbpYJv1woS94PQGq` はSHA `b3c3554` からREADY。project SSO protectionがpreview deploymentsに有効で、匿名アクセスはVercel loginへredirectされるため、previewの `/readyz` runtime応答は未観測。
- Production aliasはdeployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`、`main` SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` を配信。実測は `/healthz`=200、`/readyz`=404、unauthenticated `/mcp`=401。PR未レビュー・未mergeのためproductionは旧revision。
- Vercel env metadataのnames-only照会 (`decrypt=false`) は403。値は読んでおらず、preview/production runtime変数の有無は未確定。ローカルにVercel CLIはない。
- 前回依頼した一時Vercel share linkの読み取り利用許可は未回答のため作成していない。ChatGPT workspace eligibility、OAuth grant、tool discovery、CPU run、別会話からのresult/artifact取得はすべて未受入。AcceptanceはNOT RUN。
- P0/P1/P3/P4/P5のローカル実装・CI証拠とproduction/ChatGPT/provider受入れを混同しない。P3 host/region/public origin/cost ceiling/notification SLOも未決。`policies/repository-state.yaml` は `mode: parked` のまま。有償provider callやspendなし。
- 117-path変更はPR #51へpush済みで、既存file-ownership mapに従ったreview evidenceはある。ただしP1/P3/P4/P5を一つのDraft PRに含むため、 roadmapの「小さい複数PR」に整理する項目は未完了。履歴を書き換えるforce pushはせず、GitHub review前にPR分割が必要ならブランチ戦略を別途判断する。

これより下の 2026-10-28 snapshot/log は各記載日の履歴であり、現在のbranch/PR/runtime stateとして再利用しない。

## 継続時の現在状態 — 2026-10-28 11:49 UTC

Codex goal is active for the complete roadmap; continue from the current
checkout rather than restarting P0 or the already implemented local CPU
vertical. Current branch/HEAD: `codex/chatgpt-cpu-vertical` /
`f054aebe96460fe033dde8d91d7e3bbab0255655`. The worktree has 75 tracked
modified/deleted and 42 untracked paths, zero staged; the current slice map
assigns all 117 paths exactly once. `git diff --check` passes. Existing remote
CI is for the pushed head only. Existing Codex Security scans are snapshot
specific and do not establish coverage of this exact current worktree.

Keep `policies/repository-state.yaml` parked. The ChatGPT/Platform browser
session is logged out; workspace eligibility and tunnel/OAuth association
remain unverified. The earlier Bugbot-vs-Security-Review single-choice request
is still awaiting the user's answer. Continue with work that does not depend on
that choice, but do not start the selected review until it is supplied. No
provider call, spend, deployment, production DB change, push, or merge is
authorized by this handoff.

Immediate sequence: refresh the exact path/diff snapshot and review map; after
the review choice, review and prepare the current changes for a reviewable PR;
then complete real ChatGPT CPU acceptance and owner-selected P3 host acceptance.
Only after CPU/operations acceptance proceed to one separately bounded P4 GPU
validation. P5 remains a separate explicit paid-authorization gate. Record
offline, local Docker/PostgreSQL, ChatGPT, target-host, provider, and paid-run
evidence as distinct scopes.

P0 baseline audit、P1 T1-T5のlocal CPU lifecycle、P2 local recovery/backup implementation、P4 offline capability-selection sliceは実装済みだが、それぞれのproduction/ChatGPT/GPU acceptanceとは区別する。主要slice commitsはHTTP `311d6a9`、CPU/MCP/recovery `7c4454b`、OAuth `c8172c0`、P3 operations `d794c13`、CI/package `cccfcb8`。Draft PR #51 headは `f054aebe96460fe033dde8d91d7e3bbab0255655`（121 files、+13,040/-215）。PRはOPEN/DRAFTで、GitHub reviewは未着。GitHub CI、Gateway offline、Gateway comment bridge、Project bridge、Vercel preview関連checksはremote headでsuccess。Vercel protected-URL fetchでpreview runtimeを再確認済み: `/healthz`=200だがconfigured/auth_configured=false、`/readyz`=503で6 readiness項目すべてfalse、OAuth protected-resource discovery=503 configuration_required。previewは未構成・未ready。公開production Vercelはmain SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`のまま。実ホスト、region、public origin、monthly ceiling、ChatGPT workspace write-action accessは未確定。worktreeには未コミットの `/readyz` artifact-storage readiness変更、artifact書込probe、systemd artifact権限/env分離、関連テストと文書更新がある。

最新確認: PR #51は2026-10-28時点でOPEN/DRAFT、remote headは上記SHA、60 commits/121 files、review/review thread/requested reviewerはいずれも0/null。今回のCodex Security scan `f9f8d84d-05bd-40d6-a241-d2856e841475` は同じHEADをbaseとする現worktree snapshot（digest `codex-security-snapshot/v1:sha256:d706e1d36e6e99c8408c5bd474fca42dbb7b9236d27f1304453c5408d02f82f7`）を対象に完了し、37 changed-source rows、0 candidates/findings、coverage complete。docsとtestsを除外したソース/設定差分レビューであり、runtime/host/ChatGPT/provider acceptanceではない。レポートは`docs/RELEASE_MATRIX.md`に記録。worktreeは111 paths dirty、HEADは不変、未stage。`policies/repository-state.yaml`はparked。

PR #51 current HEADの43 changed source/config/workflow inventory pathsは2026-10-28にCodex Securityで独立source review済み（0 findings、complete diff coverage）。このレビューは未コミット差分を対象にしない。レポートはCodex Security scan artifactsに保存され、詳細は`docs/RELEASE_MATRIX.md`を参照する。GitHub PR reviewは未着。preview readinessは2026-10-28 09:00 UTCにVercel protected-URL fetchで確認し、未構成・未ready。P0 baselineやlocal CPU implementationをやり直さず、`2026-10-28-gpu-control-roadmap.md` の未完了checklistから再開する。現worktreeではenabled local_cpu workloadがある場合の `/readyz` がartifact storageを要求し、実書込不能をfail-closedにする一時ファイルprobeを追加した。artifact-storageとHTTP-authの関連moduleは38件passし、Gateway全体はPostgreSQL 16とdigest-pinned CPU imageで279 passed / 2 optional skips、Starlette deprecation warning 1件。さらにsystemd unit回帰テスト10件がpassし、6 unitの`systemd-analyze verify`がephemeral Debian 12 containerで成功した。systemd結果は静的検証で、サービス起動/target host受入ではない。PR review、deployed hostのmount/quota/readiness受入、レビュー方式の選択は未完了。GPU provider追加はChatGPT CPU verticalの独立受入後、paid activationは別途明示承認後とする。

READMEが要求するworker-only provider credentialsをsystemd worker/supervisorが読めない配線漏れを修正し、optional `worker-secrets.env`を追加した。API、migration、capacity unitsには渡さず、Modal/RunPodは引き続きdisabledで実credentialも未設定。この追加後、deploy-unit tests 10件passし、6 unitの`systemd-analyze verify`もephemeral Debian 12/systemd 252 containerで成功した。これは静的検証で実サービス起動/target-host受入ではない。これを反映した未コミット差分は、既存PR #51 headのsecurity review対象外。

P3 target-host acceptanceにruntime environment isolationの確認を追加した。長時間serviceは`/proc/<MainPID>/environ`から変数名のみ出し、oneshot capacity/migrationはinstalled EnvironmentFileのパスとassignment名で確認する。値を出力・記録しない。手順は`docs/OPERATIONS.md`と`docs/CHATGPT_ACCEPTANCE.md`を参照。これはrunbook上の基準で、実ホストでの実行証拠はない。

2026-10-28 follow-up: deployment exampleの「built-in local OAuthにcookie key必須」という記述は実装と不一致だった。`LocalOAuth`はopaque sessionをDBに保存し、`Auth.fernet`はexternal OIDCだけで作ることを確認。`gateway/deploy/api.env.example`をlocal modeではキーなし、external OIDC browser loginではFernet生成値を設定する例に修正し、Gateway README/OPERATIONSとdeploy-unit regression assertionも同期した。最初のfocused pytestはactive local environmentにPyJWTがなくcollectionで停止したが、次の継続でlocked Gateway runtime dependenciesをoffline同期し、`gateway/requirements-test.txt`のpytestを戻して解消。focused deploy-unit testsは14 passed、Gateway全体289 passed/9 skipped、root全体532 passed/1 skipped。`git diff --check`と変更したPythonファイルの`py_compile`も成功。通常suiteはDocker/PostgreSQL統合設定なしで、ChatGPT/OIDC、target host、Neon/production acceptanceの証拠ではない。

以下をLunaへ渡す。これは実装開始用の指示書であり、計画作成者はまだLunaを起動していない。

## 次の作業: 実装可能な差分を閉じ、外部受入の入力を揃える

1. **最初に現worktree差分を把握する。** `git status`, `git diff --check`, `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md` と各acceptance artifactを読む。ブランチ/HEAD/digestが変わっていれば旧レビュー・旧CIを現差分の証拠に使わない。PR #51向け変更と後続分を対応付け、同一sliceのコード・tests・docsを保ったままレビュー可能な単位に分ける。作業中にstage/commit/push/merge/deployしない。
2. **Codex Securityの記録を読む。** 最新レポートは上記scan ID。0 findingsはソース差分の所見に限定され、docs/testsや実環境の保証ではない。人手レビュー、GitHub review、CIを代替しない。
3. **最初のローカル担当sliceを選び、独立レビューを閉じる。** 既存ownership mapに従いP1 OAuth/PostgreSQL→P3 operations→P4 selection→P5 gate→cross-cutting docsの順に進める。共有ファイルは表の指定ownerだけが変更する。各sliceで差分と既存証拠の対応を確認し、回帰が見つかればそのslice内で修正し、必要なfocused/full suiteと`git diff --check`を実行する（既存作業に未検証変更を混ぜない）。remote PRの古いchecksは現worktreeに流用しない。
4. **外部受入に必要な選択肢を具体化する。** P0/P3の人間入力はChatGPT workspace・role・write action権限、Secure MCP Tunnel権限または公開HTTPS host、Linux provider/region、monthly ceiling、alert recipient/SLO。これらはコードから推測しない。受入スクリプトと記録テンプレートは準備できるが、workspace・hostの実測は利用者権限が必要。
5. **順序を守る。** PR review/差分整理→実ChatGPT CPU vertical→選定hostのsystemd/DB/artifact/backup/alert acceptance→7日CPU observationを先に閉じる。そこまでGPU実行へ進まず、RunPod v2 live validationは別途限定承認を得た後、P5課金canaryはさらに明示的な個別承認後に行う。`mode: parked`、provider opt-in OFFを維持する。

### Lunaへの出力要件

- 各turnの冒頭に現在のgoal、branch/HEAD/dirty state、未完了milestoneを確認し、証拠の古さを確認する。
- 変更は小さくレビュー可能にし、ファイルownership mapを守る。ユーザーが明示依頼するまでstage/commit/push/merge/deployや外部設定変更は行わない。
- 結果は「変更内容 / うまくいったこと / 失敗・未確認 / 次の受入」に分ける。unit/offline/local Docker/production/ChatGPT/real GPUを混同しない。
- 外部設定が欠けていても独立したコード・文書作業は続ける。環境受入の未実施を理由にゴール全体を完了扱いしない。


## 2026-10-28 continuation: Modal billing-only adapter and authoritative status

A follow-up local slice added `gateway/gpu_gateway/modal_evidence.py` and 12
fake-workspace unit cases. It calls only injected `Workspace.billing.rates()`
and `summary()`, labels the result `billing_only`, marks quota evidence
unavailable, and cannot enter candidate selection. No Modal SDK/account,
credentials, provider, container, or paid resource was accessed. Focused tests
passed 12; the Gateway offline suite passed 301 with 9 environment/optional
integration skips; `git diff --check` passed. `policies/repository-state.yaml`
remains `mode: parked`. This adapter is not live provider evidence and does not
close Gateway evidence ingestion or pre-submit/worker candidate revalidation.

## 2026-10-28 P4 provider-source correction

The existing RunPod core has a real read-only GraphQL observation path in
`src/gpu_control/providers/runpod_current_pricing.py`: GPU type, VRAM, secure
hourly price, and exact datacenter `stockStatus`, bound to a reviewed contract
commit and a content digest with a maximum 300-second TTL. This corrects any
claim that the repository has no provider observation source. It is still not
complete `CapabilityEvidence` and is not connected to Gateway selection. It
does not prove CPU/RAM, runtime/OS/architecture, queue wait, result transport,
cancellation/cleanup, quota, or all-in capped cost. Local RunPod and Modal
credentials are absent; no live provider request was made.

Before implementation, revisit the Modal-first provider sequence against this
existing RunPod evidence and its separately gated credential path. Keep
unobserved fields unknown, never infer capability from workload requirements,
and do not equate datacenter stock with a reserved GPU. The eventual adapter
must persist and revalidate the exact candidate binding at prepare, submit,
and worker launch. `mode: parked` and all spending gates remain unchanged.

The first implementation primitive is now present at
`gateway/gpu_gateway/provider_evidence.py`: bounded canonical JSON envelopes,
payload digest, Ed25519 signature, key ID, 300-second maximum TTL, and optional
version high-water rejection. It is deliberately not wired to settings,
worker, DB, API, or provider calls. Next, add a persisted version/high-water
record and API-pinned public-key verification, then implement collection and
candidate binding; do not treat this utility alone as authenticated live
provider evidence.

Follow-up implementation adds schema v8 table
`gateway_provider_observations_v1`. Its Store upsert verifies the signature
before writing and refuses equal/lower versions atomically; reads check the
stored envelope digest/index fields, and a verified-read helper checks signer
and freshness. Full Gateway suite: 361 passed / 9 skipped. Still open: worker
collector and key provisioning, API-side public-key config and capability
mapping, binding creation plus submit/worker revalidation, and runtime/live
acceptance. The DB migration is additive; no provider credential, account, or
GPU was used. Preserve the parked mode and do not infer provider availability
from persisted signed data until it is wired to a live observation source.

Worker key boundary is now configured: common `gateway.env` holds the public
key JSON set; private signing key PEM is base64 in `worker-secrets.env` with a
key ID. `Settings.validate()` confirms the configured private/public pair,
and `Worker.persist_provider_observation` permits publication only from the
normal worker role, never the recovery supervisor. Deployment examples and
regression coverage enforce that the private value is absent from API config.
Focused tests: 25 passed; full Gateway suite: 362 passed / 9 skipped. Still
not connected: provider collector/scheduler, API verified-snapshot consumption
and `CapabilityEvidence` conversion, candidate plan binding, and submit/worker
revalidation. No provider calls; parked mode remains.

Latest slice (2026-10-28): strict `CapabilityEvidence.from_dict` and API
capability integration now read only signed/current stored observations,
require the exact payload shape and provider/source/timestamp binding, then feed
the selector. A fixture test confirms a verified candidate can be selected
for discovery while submission remains blocked pending live acceptance. Core
suite: 540 passed / 1 skipped; Gateway suite: 363 passed / 9 skipped. The real
RunPod/Modal collector and scheduler remain the next data-path dependency;
then bind the exact selected evidence into plans and revalidate on submit and
worker start. No provider API was called.

Live GitHub refresh: PR #51 remains OPEN/DRAFT at remote head
`f054aebe96460fe033dde8d91d7e3bbab0255655`, base `main`; all listed checks are
successful for that pushed head, and there are still no GitHub reviews. These
checks do not cover the current uncommitted worktree. The branch and its 58
uncommitted paths must be reconciled into small reviewable slices; do not stage,
commit, push, or merge until the requested handoff/repository policy is resolved.
P0 workspace authorization/actual ChatGPT connection and P3 selected-host
acceptance still require owner-side environment access. Do not weaken parked or
paid-execution gates to simulate acceptance.

---

対象はGitHub `Unjuno/gpu-control`。目的はChatGPTの会話から登録済み実験をprepare/submit/status/result/cancel/listでき、実計算の証拠を会話へ返せる製品を完成させることです。

まず次を順番に読んでください。

1. `docs/specs/chatgpt-native-experiment-control-plane.md`
2. `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md`
3. `docs/superpowers/plans/2026-10-28-gpu-control-first-vertical.md`

これらの文書は現在本体checkout内にあります。作業開始時はcheckout、working tree、PR #51 headとchecksを再確認し、未コミットの進捗文書変更を保持してください。

実装開始時には本体の `ACTION_CONSTITUTION.md`、`AGENTS.md`、`SECURITY.md`、`policies/repository-state.yaml` と関連policyを読み、mainとopen PRを再確認してください。計画時点のmainは `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`。監査PR #43はDraft/Open、headは `1699b75df8262023501d41279e83bf429dca1be4`。mainの新しいGateway実装を古い監査ブランチで置換しないでください。

当面の作業範囲はP0→P1です。P1の実ChatGPT受入が通るまで複数GPU providerの実装へ進まないでください。既存 `gateway/project_control/` のCPU隔離資産を再利用します。最初のユーザー成果は「会話から実CPU smokeを起動し、後から結果を取得できる」です。

実装は1タスクずつ、計画のFiles/Interfaces/受入条件を満たす小さいPR単位で進めてください。仕様と実装が違っていたら根拠を記録して計画を修正し、黙って要件を削らないでください。provider最新仕様と費用は着手時に公式資料で確認してください。

既存の `max_cost_usd=0` 拒否、全runブラウザ承認、非demo一律有償quote条件を、登録済み低リスクlocal CPUだけ許可する設計へ変更します。有償経路の承認やparked制約を解除する変更は別のレビュー対象です。ツール入力のapproved=true、quota推測、模擬GPU成功は使いません。

各タスク終了時に `docs/IMPLEMENTATION_PROGRESS.md` を更新してください。

```text
current_phase:
current_task:
base_sha:
working_branch:
implemented:
tests_and_commands:
real_execution_evidence:
release_matrix_changes:
remaining_blockers:
next_task:
```

実際に行った検証だけを記録し、実行層と意味的な品質を区別してください。PASS/FAIL/BLOCKED/UNCERTAINと証拠scopeを保ってください。mockテスト成功でChatGPT接続や実GPUをPASSにしないでください。

同じrunの通信再送は同じidempotency key、新しい再実験は新key。曖昧なsubmitはreconcileし、勝手に再作成しない。cancel/cleanupは新規実行OFFでも動くこと。state/owner/source/plan/result/cleanupの一致を常に確認してください。

実装・ローカル検証・レビュー可能な変更の準備を進めてください。外部設定、アカウント権限、paid activation、本番公開、mergeは現在のユーザー承認と規則に照らして判断し、追加承認が必要なら具体案と根拠をまとめ、その操作だけを止めてください。止まっている間も独立した実装や文書化を進めてください。

readiness契約とartifact書込probe、systemd artifact権限/env分離、cookie-key exampleのlocal/external OAuth差分修正のローカル実装は完了しています。これらを繰り返さず、roadmapの未完了P3から続けてください。P3 topologyは決定済みですが、provider/region/monthly ceiling/public originとworkspace write-action accessは未決です。実ホストや費用上限が未決定の間は、ホスト非依存の運用手順、復元・監視の受入設計、残るローカル欠陥の解消を先行し、実装と実環境acceptanceを混同しないでください。今回の通知bridge仕様は `docs/specs/capacity-alert-bridge-contract.md` にあり、sinkを選ぶにはhost/region/budget/origin or egress route/recipient/credential store/SLOの決定が要ります。通常suiteの最新scopeはGateway 289 passed/9 skipped、root 532 passed/1 skipped。OrbStack daemonは利用可能だが、多数の他作業由来stopped containersがあるため今回新規containerは作っていません。実host、Neon固有挙動、second-operator RPO/RTOを受け入れるには、選定環境でownershipが明確な隔離deploymentと外部決定が必要です。これらが揃うまでprovision/deploy/Neon mutationをしない。後続の新規設計が必要な段階は、その段階の受入条件と細分化計画を更新してから実装します。

2026-10-28 P3 verification refresh: Re-ran `gateway/deploy/verify_systemd_units_ci.sh` in an attributable `--rm --network none` Debian 12/systemd 252.39 container from the already-local pinned image, mounting the repository read-only and using inert placeholders. All six current systemd templates passed; no service ran and the container was removed. See `docs/acceptance/2026-10-28-systemd-uid-boundary.md`. Next task remains P3 target-host readiness/restore/quota/alerts once host, provider, region, budget, origin/egress, recipient/SLO and workspace write-action decisions are available; until then continue only independently useful source/docs verification and keep admission/provider switches parked.

2026-10-28 P3 permission correction follow-up: `check_artifact_capacity.py` only inspects mount identity and `statvfs`; the write/fsync/unlink probe belongs to API readiness. API alone joins `gpu-control-artifact-probes`; worker/supervisor access it as owner UID; capacity has only its artifact-read group. Focused deploy-unit tests passed 14/14, all six systemd 252.39 templates verified, and a fresh isolated UID/GID mode-bit matrix passed API probe/read, capacity blob-read/probe-write-denial, worker owner access, migration read denial, and API root/blob write denial. Target-host systemd sandbox/mount behavior is still open.

2026-10-28 P1/P2 integration follow-up: The full current-worktree Gateway suite now passes 296 tests with 2 optional Torch/Modal skips against a disposable PostgreSQL 16 instance and the digest-pinned CPU image. This refresh exposed missing `.gpu-control-probes` in three integration fixtures; those fixtures now model the installed artifact layout and preserve fail-closed product behavior. Worker SIGKILL-after-container-start recovery and PostgreSQL outage-after-terminal-capture recovery each passed independently and in the full suite. Root suite: 532 passed / 1 skipped; `git diff --check` passed. Evidence: `docs/acceptance/2026-10-28-local-integration-revalidation.md`. This remains local evidence, not ChatGPT/target-host/Neon acceptance.

## Current worktree review slices (base `f054aebe`, uncommitted)

The earlier 63-path slice table is superseded. The current inventory contains
111 changed paths (70 modified/deleted and 41 untracked), including the exact
file ownership of this review map. Every path is assigned once across five
sequential review slices; file membership and acceptance boundaries are listed
in [`2026-10-28-gpu-control-worktree-slices.md`](2026-10-28-gpu-control-worktree-slices.md).

Review order:

1. P1 OAuth refresh rotation and PostgreSQL concurrent-use proof.
2. P3 artifact storage, backup/recovery, Linux service identities, and capacity bridge.
3. P4 provider evidence, candidate selection, RunPod v2, result receipts, and worker revalidation.
4. P5 paid-authority trust design and the parked-mode policy boundary.
5. Cross-cutting acceptance records and roadmap/handoff wording.

The current full Gateway and root/core suites pass at their recorded local
scopes, but these checks do not replace independent review of the composed
changes or GitHub CI on the current worktree. Keep all changes local and
unstaged until the review slices and repository policy are reconciled.

---

## レビューで必ず見る箇所

- OAuthとowner境界、承認省略の範囲
- 0ドル判定とquota/料金不明時の挙動
- DB migration、旧planとfingerprintの保持
- create前intentとcrash後reconcile
- cancel/timeout/cleanupと結果の保存順序
- 無制限stdout、秘密混入、workloadによる証拠偽装
- 実ChatGPTでの受入、別会話検索、実CPU/GPUの識別

レビュー担当を別途割り当てる場合は、変更全体を曖昧に見てもらうより上記境界とexact HEADを指定する。重大な設計変更は計画を更新してから続行する。


2026-10-28 P1 queued-plan revalidation follow-up: `prepare_local` now shares an
exact current-registry check with submit; submit refuses the stored plan if the
operator manifest changed. Immediately before `backend.start`, the independent
worker reloads configured `GATEWAY_WORKLOADS_JSON` / `GATEWAY_WORKLOADS_FILE`
and compares source SHA, immutable image digest, manifest digest, execution
profile, runtime, and parameter schema. Invalid or changed configured
registry expires the queued run without creating a container. Focused tests:
local admission 14 passed; ChatGPT experiment API + local MCP 23 passed / 1
optional Docker skip. This is local regression evidence only. Current worktree
now has 58 changed paths, still uncommitted and outside remote PR #51 CI/review.


2026-10-28 follow-up found and closed one fail-open edge in that registry
check: if both worker registry environment variables were absent, the first
version skipped the comparison. Worker start now requires an explicitly
configured workload JSON/file and fails closed with
`local_workload_registry_unavailable` if it is absent or unreadable; manifest
drift uses `local_workload_changed_before_start`. Local admission tests: 16
passed; API/MCP/lifecycle/PostgreSQL modules: 23 passed / 3 skips due to the
prebuilt CPU image and dedicated PostgreSQL integration container not being
configured. The live systemd worker and API both read `gateway.env`, whose
example sets `GATEWAY_WORKLOADS_FILE`; target-host acceptance remains open.


2026-10-28 P3 capacity event-state core and outbox: Added
`gateway/deploy/capacity_event_state.py` and 23 focused tests. It validates the
fixed journal/unit identity and event schema, allowlists capacity reason codes,
rejects duplicate JSON keys and malformed persisted state, stores normalized
cursor/status with mode `0600`, uses a private process lock for state mutations,
deduplicates recent opaque cursors without ordering by wall-clock timestamps,
and atomically appends each alert/clear transition to a bounded outbox. It preserves eight
delivery attempts as bounded result/timestamp records and retains exhausted
entries and rejects inconsistent persisted acknowledgement state. Gateway
suite: 328 passed / 9 skipped / one existing Starlette
deprecation warning; root suite: 536 passed / 1 skipped. These runs did not
enable Docker/PostgreSQL integrations. A bounded `journalctl` source and
cursor-resuming poller now exist, but only fake-source behavior was exercised.
There is still no retry/backoff scheduler, sender, sink, or host notification service. Delivery is
at-least-once across the sink-accepted/local-ack crash window. The fake
journalctl source verifies bounded resume, explicit bootstrap, cursor-expiry
handling, concurrency serialization and realtime clock rollback; no Linux
journal runtime was exercised. There are now 60
modified or untracked paths in the current worktree; all remain uncommitted and
outside remote PR #51 checks. No host, provider, notification sink, or paid
resource was accessed; `policies/repository-state.yaml` remains parked.

## Current continuation checkpoint for Luna

Treat this section as the authoritative handoff snapshot; earlier dated entries
above are historical and may contain older counts or phase instructions. The
active goal is to continue the long-term roadmap toward a usable ChatGPT-triggered
registered-experiment workflow. Do not restart P0/P1 work already evidenced in
the roadmap. Follow its open P3 checklist first, then P4 live-GPU readiness,
P5 only after separate explicit paid-execution authorization, and P6/P7 after
their acceptance plans are ready.

- Checkout branch/head: `codex/chatgpt-cpu-vertical` at
  `f054aebe96460fe033dde8d91d7e3bbab0255655`; all current modified or untracked paths
  are intentionally uncommitted. Inspect and preserve every existing change;
  do not stage or commit the worktree as one batch.
- PR #51 is OPEN/DRAFT at the pushed head; its checks and prior source review
  do not cover these uncommitted changes. No push, merge, production deploy,
  host mutation, provider call, or paid resource is authorized by this handoff.
- Latest local verification: Gateway full suite with a digest-pinned CPU image
  and disposable PostgreSQL 16 bound to fixed loopback port `55543`: **344
  passed, 2 skipped**, one existing Starlette deprecation warning. Optional
  skips were Torch and Modal SDK checks. A dynamic-port attempt first exposed
  four reconnect failures after the recovery case restarted PostgreSQL; the
  fixed-port run passed. The disposable container was removed by an exit trap.
  P3 capacity/deploy-unit focused tests: **51 passed**. Artifact storage and
  HTTP readiness tests passed 40; Gateway offline suite passed 337 / 9 skipped.
  Root core suite remains 536 passed / 1 skipped from the prior selector
  checkpoint. Review correction: enabled local CPU now requires a distinct
  artifact filesystem even when the configured free-space floor is zero; the
  regression test was observed failing before the fix.
- Official Secure MCP Tunnel documentation was refreshed on 2026-10-28. It
  provides a possible private route for a bounded local ChatGPT CPU smoke before
  a public HTTPS host is selected. It requires separate Platform tunnel
  management/use permissions and association with the target ChatGPT workspace;
  documented limits are 120 seconds per request and 10 MiB serialized
  request/response. Setup and tool calls have not been attempted. Tunnel use is
  development-only evidence, not public distribution, continuous-service,
  seven-day, or large-artifact acceptance. See `docs/CHATGPT_SETUP.md` and
  `docs/CHATGPT_ACCEPTANCE.md`.
- 2026-10-28 capacity-poller concurrency follow-up: serialized bootstrap and
  full poll transactions with a separate process lock while retaining the
  existing state-write lock. Threaded pollers and a separate child process both
  verify the serialization boundary; `gateway/tests/test_capacity_event_state.py`
  plus `test_deploy_units.py` passed 45 tests with one existing deprecation
  warning. The full Gateway offline suite then passed 339 tests with 9 optional
  skips and one existing deprecation warning. No systemd service or live journal
  was exercised. PostgreSQL
  integration was rerun with a disposable PostgreSQL 16 database and pinned
  CPU image: 345 passed, 2 optional skips. The initial tmpfs-backed DB attempt
  failed the database recovery check after stop/start; the repeat used the
  image's anonymous volume and passed. All test-created DB/CPU containers and
  the DB volume were removed. Root suite was not rerun; PR checks still cover
  only the pushed head.
- P3 capacity bridge has strict event validation, a bounded no-shell `journalctl`
  source/poller, explicit bootstrap, retention-gap fail-closed handling,
  atomic `0600` cursor/status/outbox state, process-level `flock`, and a recent
  256-cursor dedupe window. Ordering follows opaque journal cursors, not
  realtime timestamps. The sink-agnostic delivery pump sends a bounded fixed
  message projection using the cursor as idempotency key and applies
  deterministic exponential backoff. `delivery_health()` exposes bounded
  counters only and does not claim human receipt or journal-reader health. An
  explicit-bootstrap/poll-once CLI and manual-only systemd oneshot template now
  run under a dedicated UID with journal read access and a private state path.
  The guarded helper passed `systemd-analyze verify` for all seven templates
  in cached Debian 12/systemd 252.39 with a read-only repository mount and no
  network. No unit start or live target-host journal has been exercised.
  There is no bridge timer, concrete sink, selected route, or notification
  acceptance. Immediate P3 work is selected-host manual bootstrap/poll
  acceptance after host authorization; connect a timer only after a sender and
  route are reviewed. Do not select a sink until provider, region,
  monthly ceiling, public origin or outbound route, recipient, credential store,
  and SLO are decided. Keep `policies/repository-state.yaml` parked.
- At each slice boundary, update `docs/IMPLEMENTATION_PROGRESS.md` and this
  handoff with observed evidence and the next concrete task. Recheck GitHub
  remote/PR state before any later integration decision. Keep local contract,
  fake-source, live-host, ChatGPT, and paid-provider evidence as separate scopes.

2026-10-28 P4 offline follow-up: workload manifests and immutable selector
requirements now include optional exact runtime identifiers and a maximum
queue-wait ceiling. Candidate evidence fingerprints supported runtimes and its
queue-wait estimate; missing/incompatible evidence fails closed. Tests passed:
core selector/capability 74, Gateway experiment API/Modal evidence/PlanV2
contract 53. Complete inventory with no admissible free GPU has explicit
`FREE_GPU_UNAVAILABLE` coverage, while incomplete inventory stays
`PROVIDER_EVIDENCE_UNAVAILABLE`; capabilities exposes registered CPU and the
unaccepted paid GPU path separately. Targeted tests passed 74 core and 53
Gateway; full root suite passed 539/1 skipped and full Gateway offline suite
passed 353/9 skipped (one existing Starlette warning). Preserve all 71 dirty
paths. No external provider or host was accessed, no live GPU ran, and parked
mode remains. Next
P4 implementation work is provenance-checked provider evidence ingestion and
exact candidate binding/revalidation at prepare, submit, and worker launch;
until that linkage exists, keep GPU selection non-submittable. P3 host
acceptance still awaits provider/region/budget/origin/notification decisions.
The Modal workload-registration section of `gateway/README.md` has also been
corrected: setup is explicitly future-only while parked, and the provider
enablement step requires a separate activation request plus reviewed policy and
all provider gates. The guide now names `runtime_requirements` and
`max_queue_wait_seconds` as operator fields.

2026-10-28 follow-up: `matches_registered_local_workload` now rejects any
`PlanV2.selection_binding`. This closes an accidental route for a P4
candidate-bound plan to enter the local CPU policy path without P4 evidence
revalidation; the same registry check runs before local worker start. Regression
observed RED before the guard; a persisted queued-plan test confirms the worker
starts zero containers. Focused local-admission/PlanV2 tests 39 passed, full
Gateway offline suite 355 passed / 9 skipped. This does not connect GPU
evidence ingestion or make GPU plans submit-capable.

2026-10-28 P4 collector continuation: a default-off, idle-worker-only RunPod
GraphQL catalog collector now exists in `gateway/gpu_gateway/runpod_inventory.py`.
It requires exact operator-mapped GPU and datacenter IDs, signs a 120-second
observation, and leaves all execution and all-in cost dimensions unknown. When
complete future evidence selects a candidate, prepare binds it into PlanV2;
submit transactionally rechecks the signed observation, and the worker checks
again before submission intent. Any change fails closed without substituting a
resource. Current provider registrations explicitly do not support
candidate-bound execution, so no candidate-bound plan can be queued yet. The
worker reads provider credentials and the private signing key from
`/etc/gpu-control/provider-evidence.env`; only the normal worker unit loads this
file. The recovery supervisor and API do not. Fake-client and signing tests
pass. Full suite after plan binding: Gateway 370 passed, 9 skipped, one existing
Starlette warning; root suite 540 passed, 1 skipped. Focused plan-binding suite
passed 82 tests. `git diff --check` and Python compilation passed.
Deployment-unit tests passed; `systemd-analyze` remains for the guarded Linux
CI runner. Do not enable the flag, install credentials, or call RunPod while
parked. Next: implement an execution backend that consumes PlanV2 and
provides trusted device/result/cleanup evidence before setting
`supports_candidate_binding=true`. Keep live-provider/GPU acceptance and
separate paid authorization as distinct later gates.

2026-10-28 P4 backend-contract continuation: Added a runtime guard requiring
candidate-bound providers to have an explicit registry opt-in, a dedicated
`start_candidate_bound` method, and capture/cleanup/is-clean lifecycle methods.
Bound jobs use only the dedicated entrypoint; a queued job with an incomplete
contract fails before submission intent/provider invocation. The default Modal
and RunPod registrations remain unsupported. Targeted offline verification:
9 Gateway tests passed; Python compilation and `git diff --check` passed. This
is contract-shape evidence only, not device proof, GPU execution, result
attestation, provider cleanup, or paid acceptance. Next build a concrete adapter
and trusted device/result receipt flow, then establish provider lifecycle
acceptance before changing any registry opt-in. Keep parked mode and provider
flags unchanged.

2026-10-28 P4 result-evidence continuation: Tightened the backend contract to
require `validate_candidate_observation(run, observation)` and made worker
terminal candidate results fail closed if that trusted validator does not
return literal `True`. Invalid observations lose result/artifact payloads and
enter the cleanup lifecycle. Successful candidate GPU results must include
`gpu_used=true`, a named device, exit code zero, and normalized
`candidate_resource_verified` / `device_identity_verified` checks. The first
full Gateway run exposed a reason-precedence regression; validation now checks
signed/current candidate evidence before backend readiness, preserving stale
plan expiry. Full Gateway suite and full root suite pass. This proves only the
offline gate contract; no provider receipt, hardware, or cleanup acceptance
exists. Next implement a provider-authenticated receipt verifier that binds the
actual resource/device, run ID, plan fingerprint, immutable image, and result.
Keep provider registry opt-ins false and parked mode unchanged.

2026-10-28 P4 provider-receipt continuation: Added the gateway verifier for
Ed25519 execution receipts with distinct `provider` and `gateway_adapter`
signer scopes. It binds provider, exact selected
resource, run ID, approved plan fingerprint, source SHA, immutable image,
provider execution ID, device identity/model, GPU-use/exit claims, and the
normalized result digest. Receipt trust keys are configured separately from
Gateway worker observation-signing keys through
`GATEWAY_CANDIDATE_RECEIPT_PUBLIC_KEYS_JSON`. Worker persists the signed
receipt and adds resource/device markers only after signature and adapter
live-object validation. The provider-facing contract is documented at
`docs/specs/p4-candidate-execution-receipt-contract.md`. Fake-signature cases
cover valid binding, tampering, wrong resource/fingerprint/result, untrusted
key, and expiry. Focused Gateway modules passed 49 tests; full Gateway and root
suites, Python compilation, and `git diff --check` passed. No provider receipt
support, key provenance/rotation, account quota, GPU, billing, or cleanup was
verified. Keep Modal/RunPod opt-ins false, provider switches disabled, and
parked mode. Primary provider docs expose authenticated API identity fields but
no signed receipt in the reviewed interfaces. The verifier distinguishes an
adapter signature over an authenticated API snapshot from a provider signature;
the adapter must perform a live object/result cross-check and its key provenance
must be independently established. No GPU submission is currently supported.

2026-10-28 provider-source check: Current official RunPod GraphQL schema exposes
Pod/machine/GPU identity and telemetry through authenticated queries; reviewed
schema did not define a provider-signed result receipt. Modal Sandbox docs expose
Sandbox identity, poll/streams/termination, and `MODAL_SANDBOX_ID`, but no
provider-signed hardware/result receipt in the reviewed interfaces. Sources and
scope are recorded in `docs/specs/p4-candidate-execution-receipt-contract.md`.
No credentials or provider APIs were used. The receipt verifier now includes
separate signer namespaces and checks for provider signatures versus adapter
signatures over authenticated API snapshots. No adapter signer key or provider
adapter has been provisioned/accepted; never present adapter evidence as
provider-signed.

2026-10-28 receipt signer-scope implementation: The verifier now represents
`provider` signatures and `gateway_adapter` attestations as distinct signer
values, validates namespaced key IDs, and requires an evidence-source ID plus
provider-object snapshot digest. Adapter attestations remain claims by trusted
adapter code after its independently authenticated live API check; they are
not called provider-signed. The contract and env example are updated. Focused
receipt tests: 9 passed; full Gateway and root suites passed, as did
`git diff --check` and Python compilation. No adapter key, provider adapter, or
live evidence is configured. Keep GPU blocked and parked mode. Next implement
a provider-specific adapter only after reviewing its authenticated API fields,
result transport, costs, uncertainty/reconciliation, cancel, and cleanup against
this explicit evidence model.

2026-10-28 candidate receipt read-path continuation: `ExperimentService` now
re-verifies successful candidate GPU receipt signatures, run/plan/resource
binding, normalized result digest, and ResultV2 success claims whenever the run
is returned by get/status/result, terminal idempotency reads, or list. Historical
reads allow receipt TTL expiry but still require a valid signature, bounded
original validity window, no future issue time, and exact result identity. If
stored candidate success is tampered, the API reports
`failed/result_integrity_failed` and redacts the untrusted result; artifact
retrieval consumes this verified run response. Focused read/receipt tests: 11
passed; full Gateway and root suites, Python compilation, and `git diff --check`
passed. This is offline trust/tamper evidence only. Provider adapter, trusted
production keys, actual GPU, and ChatGPT retrieval remain unaccepted. Keep mode
parked and all provider switches off.

2026-10-28 candidate cleanup invariant follow-up: Successful candidate GPU
results now require `cleanup_state=complete`, and the API checks the same field
on every successful result read. Post-persistence mutations to metrics or
cleanup state return `failed/result_integrity_failed` with the untrusted result
redacted. Focused candidate/read/contract modules passed 29 tests; full Gateway
and root suites, Python compilation, and `git diff --check` passed. This proves
only the stored-state invariant and current worker `cleanup`/`is_clean` flow;
there is still no independent provider cleanup receipt or live resource absence
proof. Adapter cleanup attestation, provider/GPU acceptance, ChatGPT acceptance,
and parked mode gates are unchanged.

2026-10-28 P5 paid-execution separation: Added an independent
`supports_paid_execution` provider-registration flag. Candidate plans with
PAID/CREDIT_BACKED/other nonzero-or-unknown cost evidence cannot use the P4
candidate capability alone. Submit rejects them unless paid execution has its
separate registry acceptance; the worker additionally calls a trusted
`validate_paid_authorization(run)` before writing submission intent or invoking
the provider. Missing, false, or raising permit validation fails closed. This
is the Gateway hook for the existing core `LiveExecutionPermit`, not the permit
implementation itself. Focused registry/API/recovery tests: 39 passed; full
Gateway and root suites, compilation, and `git diff --check` passed. No
RunPod/Modal opt-in, live authorization, credential, provider, GPU, or billing
activity occurred. Next implement the trusted bridge that validates a
run-specific core permit against the exact Gateway plan and fresh pricing /
occupancy / result-transport evidence, then independently review it before any
registry flag changes. Keep parked mode.

P5 permit gate regression follow-up: Added a worker integration test using a
valid current candidate snapshot and PAID PlanV2. A registration may advertise
paid acceptance in the fixture, but a backend rejecting the run-specific permit
is stopped before submission intent or provider start, and its queue slot is
released. Zero-cost classifications are now provider-aware: remote providers
require `FREE`/`FREE_QUOTA` plus exact zero additional cost; `LOCAL` only works
for local provider IDs. Full Gateway and root suites pass, as do compile and
diff checks. The current RunPod core `LiveExecutionPermit` has not yet been
wired into a Gateway backend. No live provider/paid execution; parked mode.


2026-10-28 P5 permit-bridge boundary: Added
`docs/specs/p5-gateway-runpod-permit-bridge.md`. Do not wire the Gateway by
serializing the existing core `LiveExecutionPermit`: it is an unsigned dataclass
and its authority comes from GitHub protected workflow/Environment evidence.
Gateway persists browser approval only and has no durable paid envelope. Next
select and threat-model an independent paid-authority issuer for ChatGPT runs,
then define signed run-specific envelope, exact PlanV2/core-plan mapping,
durable storage and worker/pre-create validation. Browser approval remains a
separate prerequisite; do not synthesize core Human/PaidAuthorizationEvidence
from its fields. No provider switches or parked policy changed.

### Continuation revalidation — 2026-10-28 08:25 UTC

- Local state remains branch `codex/chatgpt-cpu-vertical`, HEAD
  `f054aebe96460fe033dde8d91d7e3bbab0255655`, with 105 modified/untracked
  paths; preserve them and do not batch stage/commit.
- Current local full Gateway Docker/PostgreSQL 16 run passed 395 / 2 skipped.
  Current snapshot source scan covered 36 changed source-like files over eight
  surfaces, zero candidates; it is not a GitHub human review or deployed
  validation. Details/report are in `docs/IMPLEMENTATION_PROGRESS.md`.
- Read-only GitHub refresh at 08:25 UTC: PR #51 OPEN/DRAFT, head still matches
  local HEAD, base `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, zero reviews and
  review requests; `main` is unprotected. No GitHub state changed.
- Next: resolve the PR review gate through normal human review and keep the
  local slices reviewable; independently, obtain intended ChatGPT workspace
  eligibility/access and P3 host/region/origin/cost ceiling before live
  acceptance or deployment. Until those facts are available, continue offline
  work on the remaining P3 checklist, keeping local contract evidence distinct
  from host/ChatGPT acceptance. Keep repository mode `parked`; no paid/GPU
  execution or provider calls.

### P3 delivery boundary clarification — 2026-10-28

The capacity event implementation ends at a validated durable outbox plus an
injected, bounded delivery pump. `gpu-control-capacity-bridge.service` only
polls journald with `PrivateNetwork=true`; it does not dispatch and is not a
notification service. There is no sender, timer, sink, host, route, recipient,
credential store, or SLO selected. Do not invent one. Continue reviewable
sink-neutral P3 work; after the operator selects those deployment inputs,
implement the corresponding bridge-only sender/service and verify alert plus
clear delivery on the target host. See the implementation-progress entry and
`docs/specs/capacity-alert-bridge-contract.md`.

### P3 retention-gap recovery implementation — 2026-10-28

The manual capacity bridge now supports explicit `--reconcile-latest` after a
saved journal cursor is vacuumed. It requires the cursor to be absent on both
sides of a bounded latest-event read, preserves pending outbox records, and
reannounces current status; missing intermediate transitions remain unknown.
Operations and contract docs describe the operator procedure. Fake-journal
capacity, backup, and systemd template regression suites passed 71 tests with
one existing Starlette deprecation warning. Evidence:
`docs/acceptance/2026-10-28-capacity-retention-reconciliation.md`. This is not
live host or notification acceptance. Next review this P3 slice, then continue
with remaining independent P3 host-independent acceptance preparation; selected
host, notification sink/route/SLO, and ChatGPT workspace decisions remain open.

Retention-recovery review follow-up: independent focused review found the
runbook used unsupported `sudo -G`; removed it and rely on the documented
`usermod --append --groups systemd-journal` identity setup. The corrected
runbook was followed by a green 71-test focused suite. The Linux command has
not been executed on a target host. Current local worktree has 106 modified or
untracked paths; preserve them. This slice is ready for human review, not merge
or host acceptance.

### P3 bridge health inspection — 2026-10-28

Added `--show-health`, a read-only local outbox counter command which never
constructs a journal source and prints no cursor/event reason. Its regression
was observed failing before implementation; the focused capacity, backup, and
deploy-unit suites then passed 72 tests, with one existing Starlette
DeprecationWarning. Evidence:
`docs/acceptance/2026-10-28-capacity-bridge-health-cli.md`. This is not live
monitoring or delivery acceptance. Continue remaining host-independent P3
work while host/sink/SLO and ChatGPT workspace choices remain open.

Health CLI review fix: the independent reviewer caught that `--show-health`
read state outside the fixed-error boundary. It is now guarded; corrupt state
returns a fixed error with no path/parse detail and no journal access. The
corruption regression passed along with the focused 73-test capacity/backup/
deploy-unit suite; `git diff --check` passed. See
`docs/acceptance/2026-10-28-capacity-bridge-health-cli.md`. No Linux host,
journal, sink, or delivery service was used.

P1 OAuth refresh correction: added a RED regression for rejected scope
expansion consuming the old refresh token, then made scope validation precede
mutation and token-family replacement atomic. Fault injection verifies an
insert failure preserves the original pair and creates no partial replacement.
OAuth modules passed 37; full offline Gateway passed 395 / 9 skipped. Evidence:
`docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`. PostgreSQL 16
concurrent-use regression also passed 1/1: one refresh succeeds, the second
gets `invalid_grant`, and persisted token state is consistent. Neither test
proves deployed database behavior or live ChatGPT acceptance. Continue pursuing
the target workspace connection rather than treating offline protocol evidence
as P1 completion; keep provider/paid gates parked.

Full current-worktree validation follow-up: with the stoppable PostgreSQL
container and digest-pinned CPU image, Gateway passed **403 tests / 2 optional
skips**, including the OAuth race and PostgreSQL outage recovery. The first
attempt used `docker run --rm`; the intentional DB stop removed the test
container, so that invocation was discarded. The corrected invocation omitted
`--rm`, passed, and removed its dedicated container. Root/core then found a
YAML implicit-date type mismatch in the RunPod retirement-date field; the field
is now explicitly quoted, and the full root suite passes **549 / 1 optional
skip**. Scope, inventory digest, and exact limitation are in
`docs/acceptance/2026-10-28-local-integration-revalidation.md` and
`docs/IMPLEMENTATION_PROGRESS.md`. The older 63-path slice table above is a
historical inventory, not a complete assignment of the current 110-path
worktree; refresh that map before independent review. No ChatGPT workspace,
target host, Neon production database, provider API, GPU, or paid path was used.

P3 static-systemd follow-up: re-ran the guarded helper in the cached Debian
12/systemd 252.39 container with network disabled and a read-only repository
mount. All seven current service/timer templates passed (`systemd-analyze
verify`, exit 0, no diagnostics); helper and capacity bridge hashes match the
recorded snapshot. No service started. This does not verify service startup,
mount namespace permissions, journal access, or target-host delivery. See
`docs/acceptance/2026-10-28-systemd-uid-boundary.md`.

Read-only gate refresh 2026-10-28 08:42 UTC: PR #51 is still OPEN/DRAFT at
`f054aebe96460fe033dde8d91d7e3bbab0255655` with no reviews; all listed checks
succeed only for that pushed head. `main` remains unprotected. Current local
worktree has 110 modified/untracked paths and is not covered by remote CI. Do
not stage, commit, push, or merge from this continuation. Actual P1 acceptance
still requires intended ChatGPT workspace access; P3 host/route/cost/SLO inputs
remain operator-owned. Keep offline work evidence scoped and all execution gates
parked.

P3 runbook syntax pass: all 19 fenced shell blocks across `docs/OPERATIONS.md`,
`gateway/README.md`, and `docs/CHATGPT_SETUP.md` pass `bash -n`; none were
executed. This adds no host-acceptance evidence.


## 2026-10-28 preview runtime evidence refresh

Vercel protected-URL fetch confirmed that the current PR preview is reachable but unconfigured: `/healthz`=200 (`configured=false`, `auth_configured=false`), `/readyz`=503 (database, migration, worker, supervisor, registry, authentication all false), OAuth protected-resource discovery=503 `configuration_required`. Continue with offline implementation/review and treat this as a deployment configuration/service prerequisite; do not mark ChatGPT acceptance passed.

## 2026-10-28 latest continuation evidence

Revalidated current worktree slices before continuing: OAuth/auth modules **37
passed**; PostgreSQL 16 one-time refresh-consumption race **1 passed**;
artifact/backup/capacity/permission/systemd regression modules **91 passed**;
all seven systemd templates passed the guarded Debian 12/systemd 252.39 helper;
root/core suite **549 passed / 1 skipped**; complete Gateway suite with digest-
pinned PostgreSQL 16 and local CPU container **403 passed / 2 optional skips**.
The focused and full integration records are linked in `docs/RELEASE_MATRIX.md`
and `docs/IMPLEMENTATION_PROGRESS.md`. No service or live provider was started;
all dedicated test containers were removed. `git diff --check` passes; HEAD
remains `f054aebe96460fe033dde8d91d7e3bbab0255655`, 111 paths remain dirty and
unstaged, and repository policy remains parked.

Do not repeat P0 baseline, local CPU lifecycle, or offline P4 selector tests
without a changed source snapshot. Next execution order remains: finish
independent review and compose reviewable slices; obtain the owner's ChatGPT
write-action workspace choice and P3 host/region/cost ceiling/public origin/
alert route and SLO; then perform the authorized ChatGPT CPU and target-host
acceptance. P4 real GPU is downstream of CPU operational acceptance; P5 paid
execution requires its own explicit authorization. No reviewer request, branch
push, merge, host provisioning, DB migration, or deployment was performed.
