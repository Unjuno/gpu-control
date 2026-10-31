# Lunaへの実装引き継ぎ

## 最新チェックポイント — 2026-10-31 02:22 UTC

- 作業ブランチは `codex/chatgpt-cpu-vertical`、HEAD は
  `a794438f42bd7246f463eaaa40d963af0aae9d13`。作業ツリーは91 pathが変更
  または未追跡。primary checkout上の既存作業を消去・reset・stashしない。
  policyは引き続き `mode: parked`、live paid computeとRunPod live callsは
  `false`。
- `gateway/gpu_gateway/app.py` には `/readyz` があり、DB/schema、workerと
  supervisor heartbeat、registry、auth、local CPUのartifact storage/admission
  を確認する。`gateway/vercel.json` はFastAPI frameworkを指定する。現在の
  本番HTTP観測は `/healthz`=200、`/readyz`=404、未認証`/mcp`=401。この404は
  local routeの未実装ではなく、レビュー済み候補と本番revisionの未一致として
  扱い、まず配信revisionを確定する。
- 読み取り専用のGitHub確認ではPR #51–#59はOPEN/DRAFTで、各headの9 rollup
  entries（7 Actions checks、Vercel deployment、Vercel Preview Comments）が成功。
  #52は`REVIEW_REQUIRED`、他はreview decisionなし。PR #43も
  OPEN/DRAFT、5 checks成功、`REVIEW_REQUIRED`。これらはdirty checkoutを検証せず、
  mergeや独立reviewの代わりにならない。
- 現行の作業ツリーと候補のローカルsuite記録は
  `docs/acceptance/2026-10-31-pr51-full-current-candidate.md` と関連acceptance
  filesを参照する。これらはGitHub CI、ChatGPT OAuth/CPU実行、production readiness、
  real GPU、paid executionを証明しない。
- 現行91-path treeとPR #51–#59 sliceをファイルごとに比較した結果は
  `docs/acceptance/2026-10-31-pr-stack-reconciliation.md`。6 pathだけが既存slice
  headとblob一致、39 pathは同じパス上で内容が分岐、46 pathは現行slice外。
  そのため既存Draft PRへ一括反映せず、このレポートの分類を起点にmigration/workerの
  依存を保って新しいreview境界を組み直す。
- 現行treeを`origin/main` `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`から再生する
  219-path patchは`/tmp/gpu-control-main-current-20261031-reconciled.patch`。
  disposable indexで生成し、現行treeへのreverse preflightは成功。これはfull-tree
  再構成であってreview sliceではない。新しいレビュー範囲ごとのCI/approvalは未取得。
- より小さいレビュー構成はPR #58 head `561a6c7ac697dfdf22f304b60e313fccb2c806a4`
  から15 patchを順番に適用して現在の94-path deltaと完全一致することを再生確認した。
  既存6候補、P1/P3/P4/P5/cross-cutting追加5候補、同じslice内の更新4候補の構成と
  scope limitは`docs/acceptance/2026-10-31-pr-stack-reconciliation.md`を参照。
  パッチは`/tmp/gpu-control-slice-*-on-561a6c7.patch`および
  `/tmp/gpu-control-current-on-561-*.patch`にある。これはツリー再生確認であり、
  追加P4/P5コードの新規テスト、GitHub CI、独立reviewを意味しない。
- 次の作業順: (1) 現行91-path差分を既存PR stackの正確なhead/親/レビュー範囲に照合し、
  依存順を保ったレビュー単位をローカルで確定、(2) 独立reviewとheadごとのCI後に
  readiness対応revisionをdeployして認証付き`/readyz`を確認、(3) eligible ChatGPT
  workspaceでOAuth/DCR・CPU実行・別会話result取得を受入、(4) P3 target-host運用と
  7日観察、(5) P4 real GPU smoke、(6) P5 paid-authority issuer/revocation/permit bridge
  の独立脅威レビューと別途明示承認。承認済みでない外部変更、deploy、provider call、
  支出を行わず、各段階の根拠と失敗層を記録する。

## Historical continuation evidence — 2026-10-31 (superseded by latest checkpoint above)

- Current checkout is `codex/chatgpt-cpu-vertical` at `a794438`, 55 commits
  ahead and 56 behind its configured upstream, with 68 unstaged tracked and
  untracked worktree paths. Preserve the dirty worktree and parked policy.
- Current Gateway offline suite passed 484 tests with 15 skips; focused credit
  and paid authorization suites passed 52 tests. This does not replace the
  earlier exact-source Docker/PostgreSQL CPU record or any live acceptance.
- The P4 signed credit verifier is offline only; no provider implements its
  hook. Its issuer settings are empty by default. Independent review covered
  the initial verifier/config diff; two final guard checks were added
  afterwards, so review the current final diff before treating it as reviewed.
- PR #57/#58 are OPEN/DRAFT with no GitHub reviews. Their latest GitHub
  workflow runs and Vercel statuses succeed, but none cover the dirty local
  worktree. The visible ChatGPT browser is logged out.
- PR #58's schema-v9 follow-up fails to apply directly to #57 and a three-way
  replay conflicts because schema-v9 depends on #51's schema-v8 provider
  observation migration. Keep the v8/v9 ordering explicit when splitting the
  review stack; do not advertise #58 as independently mergeable after #57.
- A bounded P1 admission-aware `/readyz` follow-up was reconstructed on an
  isolated worktree at exact PR #57 head. Candidate patch is
  `/tmp/gpu-control-p1-readiness-on-57.patch` (SHA-256
  `03edebebd511a341272b6cd66bcdd5c597d69a8f7c5ff84bd40d54fe738eb118`); its
  exact candidate-source Gateway suite passed 246/9 skipped after verifying
  both Gateway and shared Core imports resolve inside the candidate worktree.
  Acceptance scope is recorded in
  `docs/acceptance/2026-10-31-p1-readiness-review-candidate-on-57.md`. The
  candidate has no GitHub CI or independent review and is not deployed.

## 継続ゴールと現在地（2026-10-28、PR state・運用差分再確認）

最終ゴールは、ChatGPTの通常会話だけで登録済み実験のprepare/submit/status/result/search/cancelを行い、同じjobの実行・復旧・成果物を正確に返すこと。長期ロードマップの順にP3運用、P4実GPU、明示承認付きP5有償、P6再現可能な研究実験、P7保守へ進む。実装計画の現行スナップショットと次の順序は `2026-10-28-gpu-control-roadmap.md` を参照。

## 最新状態 — 2026-10-31 PR stack refresh 21:02 UTC

### Exact full-source candidate refresh — 2026-10-31

After that snapshot, reconstructed the full primary checkout at
`a794438` (including its 61 dirty/untracked paths) on a detached worktree at
PR #51's exact current head `e3ffcef`. All 339 files matched byte-for-byte.
The full candidate passed Gateway **482/2 skipped** using PostgreSQL 16 and a
digest-identified CPU smoke image, plus Core **559/1 skipped**. See
`docs/acceptance/2026-10-31-pr51-full-current-candidate.md` and
`docs/IMPLEMENTATION_PROGRESS.md`. A prior 61-path-only replay omitted
committed source differences and is superseded; do not quote its 471/2 result
as full candidate evidence.

PR #51–#59 remain the existing OPEN/DRAFT stack and no GitHub review has been
submitted. The reconstructed patch has no GitHub CI result. Continue by
mapping the full candidate diff against the exact existing PR ranges and
review coverage before preparing any PR action. Preserve the primary dirty
worktree, parked policy, and all provider/spending gates.

### Current base selection and candidate slices — 2026-10-31

PR #58 head `561a6c7ac697dfdf22f304b60e313fccb2c806a4` is the preferred base
for the next local candidate: six of its seven changed-path final blobs match
the current checkout, including schema-v9 OAuth. Reconstructing the full
source at this base matched all 340 files. The current net tree delta is 61
paths and has six disjoint replay slices: P1 OAuth/readiness (7 changed
paths), P2 recovery (2), P3 operations (11), P4 provider contract (9), P5
offline authorization (11), and cross-cutting/CI (21). Exact per-slice patch
fingerprints and local test scope are in
`docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.

Focused validation on this source state: P1 56 passed; P2 worker crash recovery
1 passed; combined P3+P4 48 passed; P5 Gateway 77 passed and Core 38 passed.
The exact-code full suite from the preceding PR #51 based replay passed
Gateway 482/2 optional skips and Core 559/1 Python-version skip. P3 and P4
must remain one merge candidate unless a full-suite replay proves they are
independently integrable; earlier P3-only candidate runs had four failures.
PR #58 and its parents are still unreviewed Draft PRs, so this is only the
best local reconstruction base, not an approval or GitHub-CI result.

> **2026-10-31 continuation refresh:** The local checkout is at
> `a794438f42bd7246f463eaaa40d963af0aae9d13`; it has 41 modified tracked
> paths and 16 untracked paths (57 total), all unstaged. The source-matched
> current-worktree Gateway/Core suite is 480/2 skipped and 550/1 skipped;
> focused PostgreSQL OAuth/migration, backup-manifest, and worker-crash checks
> passed 7/7, 1/1, and 1/1.
>
> PR #52 head `bc9b0305e6b2e86f9d8c214161b10511ce9f012c` has 43 files and
> all seven exact protected check contexts plus Vercel passing. The original
> P1 Security Review covered `c824b90`, not the new workflow files. PR #52
> remains Draft with one required GitHub approval outstanding.
>
> PR #53 (19 files), #54 (21 files), #55 (38 files), and #56 (25 files) have
> successful recorded Actions contexts and Vercel. PR #57 is the P1 CPU
> lifecycle/OAuth migration slice at `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`
> (54 paths); its seven standard Actions contexts and Vercel pass after the
> clean Gateway CI jobs explicitly installed the repository package. The
> selected read-only Security Review found no reportable issues. The stacked
> base reports no required contexts with `gh pr checks --required`; main still
> requires independent approval when the series reaches it. PR #52 remains
> Draft with one approval outstanding.
>
> PR #51 now follows #57 at
> `3346d0818dd1dd195d8105c348f00b51e2879daa` (145 files); its old checks are
> stale after retargeting. It remains an aggregate. No PR has a GitHub review.
>
> PR #58 is a focused P1 OAuth DCR/schema-v9 follow-up at
> `cb37a630e1609b6166bc0122f3aba86a759beb50`, stacked on #51. Its seven
> standard Actions contexts and Vercel pass. Gateway CI passed 428 tests with
> one skip and one warning, including the PostgreSQL 16 and local CPU path;
> candidate-source OAuth/migration tests passed 17/17 locally. #58 remains
> Draft without a GitHub review and cannot be independently merged until the
> #51 parent stack is reviewed and split.
>
> Production `/readyz` remains 404; the latest unauthenticated probe also
> returned `/healthz`=200, OAuth discovery=200 and `/mcp`=401. The PR preview is SSO protected;
> unauthenticated probes reached Vercel login, not the Gateway runtime.
> ChatGPT remains logged out and authenticated acceptance remains open. Keep
> repository mode `parked`; do not use live GPU or paid execution.

- Checkout `codex/chatgpt-cpu-vertical` remains at `aa681f4062dac6b73bcf380a38a4258b96a47e1`. Current worktree has 19 modified tracked files and 9 untracked files; nothing staged or committed. The current uncommitted Gateway source fingerprint and full-suite evidence are recorded in `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md` and `docs/acceptance/2026-10-30-dirty-source-paired-restore.md`.
- Twenty local-only candidate checkpoint refs span the P1 CPU vertical through the 121-path foundation at `f054aebe`; names run from `codex/gpu-control-p1-01-baseline` through `codex/gpu-control-stack-20-foundation-evidence`. Fresh ancestry checks confirm the refs are sequential ancestors, but several commits have intermediate parents; these refs are historical checkpoints, not automatically valid PR boundaries. Use the explicit base/head ranges in `2026-10-28-gpu-control-worktree-slices.md` and recompute their changed paths. Focused changed-test subsets for checkpoint ranges 15–20 are now recorded there; full CI per proposed PR and independent GitHub review remain open. None of these local checkpoints has new GitHub CI or an independent GitHub review.
- PR #51 remains OPEN/DRAFT at head `aa681f4`, `REVIEW_REQUIRED`, with zero reviews. The seven required Actions contexts and Vercel passed on the pushed head; they exclude current worktree changes. Live `main` protection confirms strict checks for Python 3.11/3.12/3.13, Trusted reference container, Gateway offline, Gateway comment bridge, and Project bridge. No GitHub write was made.
- Latest public alias GETs (2026-10-30 16:59 UTC) returned `/healthz` 200 (`configured=true`, local OAuth), `/readyz` 404, protected-resource discovery 200, and unauthenticated `/mcp` 401. Read-only Vercel deployment metadata now identifies the READY PR preview as exact pushed HEAD `aa681f4` and production as `main` at `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. This establishes source provenance for those deployments, not runtime health; the local dirty changes are in neither deployment. The public production `/readyz` 404 remains the failing layer. No authenticated preview fetch was made. Evidence is recorded in `docs/CHATGPT_ACCEPTANCE.md`.
- The current dirty Gateway source was revalidated with a CPU image whose Dockerfile source files match byte-for-byte and pinned PostgreSQL 16. Gateway passed **427 / 2 optional skips**; Core passed **550 / 1 Python-version skip**. The recorded Gateway dirty-source fingerprint is `06dc2a2d9b48d146d0dc45a650feacaa7949ff7860eb4fba25c6bc1cfd605877`. Earlier harness runs are explicitly excluded: wrong image variable, fixture revision mismatch, and auto-removing test database. This remains local evidence, not GitHub CI or production acceptance.
- The current checkout's separate trusted reference workload also passed locally in a uniquely named, fully constrained Docker container; the sentinel stayed out of container env and the exact local image/container were cleaned up. It is not an Ubuntu GitHub Actions result. Record: `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md`.
- Replayed Gateway comment bridge and Project bridge required-check payloads locally on this checkout: Gateway modules **81 passed / 1 optional Torch skip**, tiny-LM real Docker fixture passed with lower loss and `gpu_used=false`; Project bridge **19/19** and its real Docker smoke passed with lower loss and `gpu_used=false`. Containers and temporary image tags were removed. These are local arm64 checks, not GitHub Actions or PR review.
- The same dirty Gateway fingerprint now also passed a real PostgreSQL 16 schema-v8 dump/verify/restore path: one synthetic DB run and artifact were paired, restored into another database/tree, and fetched byte-exactly through `ArtifactStore.get()`. The systemd stopped-unit probe was stubbed; target-host acceptance remains open. Full record: `docs/acceptance/2026-10-30-dirty-source-paired-restore.md`.
- The first proposed review candidate `origin/main..c824b90` passed its complete local source suites in a fresh detached worktree. An earlier fresh Python 3.12.13 environment passed Gateway **199 / 1 optional skip**, WebMCP **3/3**, compilation, and root/Core **452 / 1 Python-version skip**. A new rerun using the primary checkout's venv without optional `modal` passed Gateway **198 / 2 optional skips** and Core **452 / 1**; both Gateway runs cover 200 tests. This is not GitHub CI or a clean locked build of the rerun environment. Exact environment and limits are in `docs/acceptance/2026-10-31-p1-c824-candidate-suite.md`.
- The final P1 CPU/recovery review candidate through `c8172c0` was rebuilt and tested with a CPU image built from its own Dockerfile and matching OCI source/revision labels. Full Gateway passed **251 / 2 optional skips** and Core **515 / 1 Python-version skip**; the earlier fresh dependency environment passed Gateway **252 / 1**, WebMCP 3/3, compilation, and Core 515/1. The rerun's extra skip is optional Modal absent in the primary venv. Exact image digest, source SHA, and cleanup are in `docs/acceptance/2026-10-31-p1-c817-source-provenance-suite.md`.
- The user-selected Security Review of the complete uncommitted diff after the child-process URL fix found no actionable findings. This local source review does not replace GitHub PR review or target-host security acceptance.
- Vercel Preview deployment `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe` is a READY Lambda built from pushed HEAD `aa681f4`, protected by SSO. The names-only Preview environment query returned 403; its runtime configuration remains unknown. No share link or configuration/deployment mutation was made. Vercel alone runs neither the persistent worker nor recovery supervisor. Production still points to `main` at `24ecb9b`; the public runtime lacks `/readyz`.
- P2 PostgreSQL + real Docker worker-crash recovery is covered locally: the child worker exits after container start and before handle persistence, and a new supervisor adopts the same container/run, stores its result/artifact, confirms cleanup, and releases the slot. The focused PostgreSQL lifecycle test passed 1/1 at the current snapshot; the latest full Gateway suite passed 480/2 skipped, as recorded in `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`. GitHub CI and target-host drills remain open.
- The P1 OAuth (3-path) and P3 backup-integrity (3-path) review candidates were each regenerated with their recorded SHA-256, applied to fresh detached worktrees, and retested against pinned disposable PostgreSQL 16. Focused outcomes were 7/7 and 25/25 respectively; temporary worktrees/DB containers were removed. These candidates are locally reproducible but are still unpushed and are not GitHub reviews or CI.
- The next P3 backup/operations candidate `c8172c0..d794c13` passed complete local suites with a CPU image built from its own labeled Dockerfile: Gateway **272 / 2 optional skips** and Core **515 / 1 Python-version skip**. Evidence: `docs/acceptance/2026-10-31-p3-d794-candidate-suite.md`. This covers local backup tooling, not a target-host restore drill, second operator, or RPO/RTO.
- The following package/CI candidate `d794c13..cccfcb8` passed complete local suites: Gateway **274 / 2 optional skips**, Core **517 / 1 Python-version skip**. Its exact-source wheel contains 23 gateway modules and four UI/WebMCP assets. Evidence and wheel hash: `docs/acceptance/2026-10-31-p3-cccf-package-candidate-suite.md`.
- ChatGPT workspace eligibility, OAuth grant, tool discovery, real ChatGPT CPU run, cross-conversation result/artifact retrieval, and owner-isolation acceptance remain NOT RUN. P3 selected-host systemd, alert delivery, second-operator recovery, and measured RPO/RTO remain open. Host/provider/region, origin, cost ceiling, alert recipient/SLO, and ChatGPT write-action access remain unresolved.
- A fresh in-app browser check at 16:43 UTC still displays Log in / Sign up. The current browser has no authenticated target workspace; this does not establish whether the user has a separate eligible workspace.
- A fresh visible in-app browser check at 17:16 UTC still displays Log in / Sign up. No target workspace OAuth/tool acceptance was run. The 178-path review-slice inventory was reconciled with no missing, stale, or duplicate assignments; see `2026-10-28-gpu-control-worktree-slices.md`.
- Preserve `policies/repository-state.yaml` at `mode: parked`. No production setting, database, provider, paid resource, GitHub PR, or deployment was changed; the twenty local candidate refs are the only branch-ref changes.
- Continue with exact review-sized candidates and evidence refresh. The complete dirty Gateway diff has now passed local Security Review and the source-matched Gateway/Core suite, but PR #51 still tests only pushed `aa681f4`. Before P1 is accepted, the readiness-capable revision must pass independent review/required CI, be deployed through an authorized path, and pass authenticated ChatGPT OAuth/tool/CPU/result retrieval. After that, finish selected-host P3 acceptance before real GPU work; keep paid execution separately gated. Do not treat green checks on pushed `aa681f4` as checks for these local changes.

## 次のLuna実行単位 — review候補の孤立検証

目的は、既存のローカル候補stackを独立PR/レビューに出せる根拠まで整え、統合漏れを防ぐこと。全体ゴールはこの作業単位に縮小しない。

1. まずprimary checkoutを変更せず、`2026-10-28-gpu-control-worktree-slices.md`の明示的なPR base/head候補（`origin/main..c824b90`, `c824b90..7c4454b`, `7c4454b..c8172c0`, `c8172c0..d794c13`, `d794c13..cccfcb8`, `cccfcb8..f15ab32`, `f15ab32..f054aebe`）について、現在の親子関係、差分path、`.github`必須CI対象を実測する。20 refsの連番をPR境界とみなさず、`4a05977`、`aa681f4`およびdirty worktreeを別のfollow-up差分として突合する。
2. 各候補は独立detached worktreeで評価し、`PYTHONPATH`と代表moduleの`__file__`が候補自身を指すことを記録する。親候補やprimary checkoutからimportした結果は無効としてやり直す。
3. P1 CPU/recoveryの提案stackは`origin/main..c824b90`、`c824b90..6646401`、`6646401..2a6f21a`、`2a6f21a..0d02058`、`0d02058..311d6a9`、`311d6a9..c8172c0`の各候補headで完全Gateway/Core suiteのローカル結果が揃っている。既知の不成立head `7c4454b`を終端にしない。P3 backup/operations candidate `c8172c0..d794c13`とpackage/CI candidate `d794c13..cccfcb8`もsource-matched imageで完全Gateway/Core suiteを通過し、候補wheelの内容を確認した。2026-10-31にmain保護APIと各workflowを読み直し、7つの必須Actions contextsと、全候補PRで全7 workflowが無条件起動することを確認済み（worktree-slices冒頭）。公開headごとの結果は独立に必要。P4 selection (`cccfcb8..f15ab32`) と P4 evidence (`f15ab32..f054aebe`) は後続機能を混ぜない。巨大な`f054aebe..4a05977`は単一PRとせず、現行ownership mapの順に累積し、完全suiteが通る境界を確認する。
4. 既存PR #51のCI成功を各候補headのCIと扱わない。各候補についてpath範囲、コマンド、テスト/skip、未解決依存、必要なGitHub CIと独立reviewを表に更新し、次にレビューへ出す最小の整合したstack順を提案する。
5. 安全制約: dirty primary checkoutを保持し、既存refを書き換えず、共有branchへcheckoutせず、勝手なstage/commit/push/merge/close/deployやprovider/API/account mutationを行わない。`parked`、全spend gateを維持する。ChatGPT workspaceやtarget hostが使えない場合も、それに依存しない候補検証を完了する。

完了時の成果物は、候補ごとの再現可能な検証記録と更新済みreview map、およびP1 real ChatGPT CPU acceptance・P3 target-host acceptanceに進むための明示的な外部前提一覧。ローカル候補のPASSをGitHub review、ChatGPT実行、実運用のPASSへ昇格しない。

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

### Verification delta — 2026-10-31 03:41 JST

The current-source P2 worker-crash-after-container-start test was rerun with
the exact current CPU image and a disposable PostgreSQL 16 database: **1
passed**. It recovered the same run and artifact, confirmed cleanup and
`active_count=0`, and left no run-labelled container. Test container was
removed and loopback port 55473 was closed. This strengthens local recovery
evidence only; target-host and ChatGPT recovery acceptance remain open. Full
details and source hashes are in
`docs/acceptance/2026-10-31-postgres-container-crash-recovery.md`.

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


## 2026-10-30 continuation: P1 OAuth candidate validation

The isolated P1 OAuth candidate at base `f054aebe96460fe033dde8d91d7e3bbab0255655`
passed its local OAuth and PostgreSQL concurrency/rollback checks: 7 passed,
0 skipped on a digest-pinned PostgreSQL 16 fixture. The exact candidate received
an independent read-only Security Review with no actionable findings. Detailed
evidence and the patch hash are recorded in `IMPLEMENTATION_PROGRESS.md` and
`2026-10-28-gpu-control-worktree-slices.md`. This does not count as GitHub
approval/CI or ChatGPT acceptance. Continue with reviewable local slices while
preserving the explicit no-stage/commit/push/merge/deploy boundary. Live
ChatGPT OAuth, tool discovery, CPU execution/result retrieval, deployed
readiness, P3 target-host acceptance, and P4/P5 gates remain open; keep
`policies/repository-state.yaml` parked.

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

## Current worktree review slices (2026-10-31 refresh)

The publishable review inventory contains 172 unique paths: 169 tracked paths
from `origin/main...HEAD` plus three new untracked files. All 16 modified
tracked worktree paths overlap the published set. The five sequential owner
slices cover these 172 paths once: P1=3, P3=49, P4=50, P5=3, cross-cutting=14,
plus 53 foundation-only paths. A historical deletion of
`gateway/deploy/worker.env.example` appears in `f054aebe..HEAD` reconstruction
patches but is absent from both `origin/main` and final `HEAD`; exclude it from
the publishable review set and candidate patches based on `main`. Exact
membership and acceptance boundaries are listed in
[`2026-10-28-gpu-control-worktree-slices.md`](2026-10-28-gpu-control-worktree-slices.md).

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

## Current continuation handoff — 2026-10-31 03:38 JST

This section supersedes the dated checkout and test snapshots above where they
differ. Read `docs/IMPLEMENTATION_PROGRESS.md`, `docs/CHATGPT_ACCEPTANCE.md`,
`docs/RELEASE_MATRIX.md`, and `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md`
for the current evidence ledger.

- Worktree: branch `codex/chatgpt-cpu-vertical`, HEAD
  `a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits ahead of local
  `origin/main` and 2 commits ahead of the pushed PR branch. Forty modified or
  untracked paths remain outside the remote PR checks/review. Preserve them;
  do not claim the PR head or its green checks cover them.
- PR #51 is still OPEN/DRAFT at remote head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, with no submitted review or
  inline comments. Seven required Actions checks pass on that remote head.
  The selected local Security Review has completed with no actionable finding
  in the current diff; this does not replace GitHub review.
- Current local evidence includes Gateway **480 passed / 2 optional skips**
  with PostgreSQL 16 and the source-matched CPU container, Core **550 passed /
  1 Python-version skip**, and this continuation's focused PostgreSQL backup
  integrity **1/1**, local OAuth/migration **17/17**, and PostgreSQL
  migration/refresh-race **7/7**. The new focused records are linked from
  `docs/IMPLEMENTATION_PROGRESS.md`. These do not establish hosted or ChatGPT
  acceptance.
- ChatGPT is logged out in the available browser. Public production responds
  to liveness and OAuth metadata, but `/readyz` is 404 and unauthenticated
  `/mcp` is 401. The protected PR preview redirects to Vercel SSO. No eligible
  workspace, OAuth grant, or ChatGPT tool call was available or attempted.
- P2 local CPU recovery and paired-backup code paths have evidence; P3
  target-host install/restore, seven-day operation, alert delivery, and measured
  RPO/RTO remain open. P3 host/region/cost ceiling/public origin/notification
  choices are unresolved. P4 still has no accepted live GPU backend; P5 is an
  offline verifier/config slice only. Keep all provider flags off and policy
  `mode: parked`.

Next order: keep preparing review-sized exact-source slices and current-source
local evidence; complete P1 real ChatGPT acceptance once an authenticated
eligible workspace and authorized endpoint are available; select and authorize
the P3 operating envelope before target-host acceptance; continue P4 only
after CPU operational acceptance. P5 paid execution still requires separate
explicit authorization and independent gates. No push, merge, deployment,
host provisioning, production migration, provider call, or paid allocation is
authorized by this handoff.

## Current continuation handoff — 2026-10-31 04:25 JST

This update supersedes the runtime and local-review observations above where
they differ. The objective remains the complete P0-P5 roadmap; do not mark it
complete from local acceptance evidence.

- The checkout remains at `a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits
  ahead of `origin/main`, two commits ahead of PR #51, with the current dirty
  paths preserved and unstaged. No commit, push, PR change, or deployment was
  made.
- The current-worktree Security Review completed on its exact snapshot with
  zero reportable candidates across five changed source files. The scan used
  sequential parent review because delegated workers were unavailable; it is
  not an independent second-reviewer result. The P5 verifier remains pure and
  unintegrated; durable one-use worker admission and pre-create revalidation
  remain future requirements.
- PR #51 remains OPEN/DRAFT at `aa681f4062dac6b73bcf380a38a4258b96a47e1`,
  `REVIEW_REQUIRED`/`BLOCKED`. Seven required checks and Vercel statuses pass
  on that pushed head only. Main branch protection requires one approval and
  those seven checks.
- Vercel production alias `gpu-control.vercel.app` is deployment
  `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ` from old `main` SHA
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. Public `/healthz` and OAuth
  discovery respond, `/mcp` requires a bearer token, and `/readyz` is 404. The
  current PR preview is READY at `aa681f4` but its health and readiness URLs
  redirect to Vercel SSO. No temporary share link or deployment settings were
  changed.
- ChatGPT acceptance remains NOT RUN: the available browser has no authenticated
  ChatGPT workspace, and the ChatGPT app surface is unavailable to this CUA
  session. P3 selected-host service/mount/alert and second-operator restore,
  seven-day CPU observation, P4 real GPU, and separately authorized P5 paid
  execution remain open. Keep `policies/repository-state.yaml` parked and all
  provider switches off.

Next local step: keep the exact-source review slices and handoff evidence
current without staging/committing/pushing. The next external acceptance
sequence requires an eligible authenticated ChatGPT workspace and approved
access to a reachable, readiness-verified deployment; P3 also needs the
operator-selected host, region, cost ceiling, alert recipient, and SLO. Once
those are supplied, run the recorded acceptance checklist. Do not spend or
provision resources until the corresponding gates are separately authorized.
Local Tunnel preflight refresh: matching environment names, expected config
paths, binary availability and container names show no Gateway origin/OAuth
client configuration, tunnel ID/runtime key, `tunnel-client`, or running
Gateway/tunnel process. No values were read. Do not start a tunnel or Gateway
for ChatGPT acceptance until the eligible workspace and Platform Tunnels
Read + Use access are available; continue independent local work meanwhile.

P4 receipt signer exact-range Security Review (2026-10-31): the two commits
from `aa681f4062dac6b73bcf380a38a4258b96a47e1` through
`a794438f42bd7246f463eaaa40d963af0aae9d13` have a completed local sequential
Codex Security review with zero reportable findings. The report is recorded at
`/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/a794438f42bd7246f463eaaa40d963af0aae9d13_20261030T192803Z_s456uisd/report.md`.
This is not an independent second review. Future adapter integration must
prove authenticated projection-to-claim correlation and private-key isolation.
P1 live ChatGPT acceptance remains open; local source review and documentation
can continue, but end-to-end acceptance needs an authenticated eligible
ChatGPT workspace and an approved reachable Gateway whose readiness is verified.
Do not change parked mode or activate paid/provider switches.

## Current-source reconstruction refresh — 2026-10-31 05:00 JST

The previous detached source reconstruction was missing one acceptance record
and had seven stale documentation files. Refreshed the isolated
`/tmp/gpu-control-main-full-current-20261031-final3` candidate from the
authoritative current checkout and compared tracked plus untracked source
files, contents, and executable bits: **339 paths, zero missing, zero extra,
zero mismatched**. Generated the refreshed `origin/main` replay patch at
`/tmp/gpu-control-main-full-current-20261031-final6.patch`. Applied it to a
fresh detached worktree at `origin/main`; `git apply --check` passed and the
resulting 339-file tree matched with zero missing, extra, or mismatched files.
`git diff --check` also passes. Do not use the earlier `final3`/`final4`/`final5`
patch artifacts. No tests were rerun; the current-source suite evidence
remains the 480/2 Gateway and 550/1 Core results above. The corrected file
inventory and replay reference are in
`2026-10-28-gpu-control-worktree-slices.md`.

This is local reconstruction evidence only. PR #51 still does not include
these changes, and GitHub CI/review, authenticated ChatGPT execution, and
target-host acceptance remain required before P1/P3 acceptance. Preserve the
primary dirty checkout and parked policy; no staging, commit, push, deploy,
resource provisioning, or provider activation occurred.

## P1 schema-v9 review candidate — 2026-10-31 05:07 JST

The current P1 schema-v9 OAuth overlay was isolated to its 10 owned paths as
`/tmp/gpu-control-p1-schema-v9-overlay-on-aa681.patch` (SHA-256
`a99aeb1184d5f6298c48d64d43a7148632642ddc1a953705f3a50c12a7a6ac1f`). It
applies to PR #51's exact remote head `aa681f4`; it fails on `c8172c0` because
the candidate predates later OAuth consent, redirect, and migration-boundary
changes in those same files. Use `aa681f4` or a newer prerequisite-complete
base. The patch is not an independently mergeable main-based PR while PR #51
remains a 169-path Draft without review. Current full-suite evidence is for
the entire dirty source, not this isolated 10-path candidate; this turn ran
no tests and requested no GitHub review. Full details are in
`2026-10-28-gpu-control-worktree-slices.md`. The exact full-source replay
patch was refreshed to `/tmp/gpu-control-main-full-current-20261031-final10.patch`
after this note was added; use that version if the cumulative snapshot is
needed.

P2 and P3 overlays were also isolated and apply-checked against the same PR
head. P2 worker crash recovery is the 2-path patch
`/tmp/gpu-control-p2_worker_crash-overlay.patch` (SHA-256
`cf9e8471f6fc3539a663d0263cc0ddabafa58f77ea88eae06e5f2ae370bd587a`). P3
backup integrity/operations is the 11-path patch
`/tmp/gpu-control-p3_backup_operations-overlay.patch` (SHA-256
`b5ac894808cf414436681cfeb2b63f3b3af70ee0cb0a419e4abf9f4c65872998`). These
are local apply-checked follow-ups on the broad PR #51 base, not independent
main-based PRs; isolated-candidate full suites, GitHub CI, and review remain
open. See the slice map for exact ownership.

The proposed eleven review ranges were rechecked against current refs: all are
ancestor-valid and their changed-path union covers all 169 current PR files.
One extra intermediate path, `gateway/deploy/worker.env.example`, is deleted
before the current PR head and must stay out of the final inventory. This
verifies range coverage only; it does not establish mergeability or acceptance.
The cumulative exact-source patch name above was refreshed again after this
handoff update.

## P1 first main-based candidate Security Review — 2026-10-31

Ran a read-only Security Review of `origin/main..c824b90` from a dedicated
worktree at `codex/gpu-control-p1-05-recovery`, following the user's selected
review type. The review reported no reportable issues and made no file changes
or test runs. This is source-review evidence for the exact 40-file candidate;
it is not GitHub approval or CI. The candidate's local full-suite record is
`docs/acceptance/2026-10-31-p1-c824-candidate-suite.md` (Gateway 198/2 skipped,
Core 452/1 skipped). The exact-source cumulative patch was refreshed after
this note; see the dated PR stack publication record below.

## Draft PR stack publication — 2026-10-31

Pushed branch `codex/gpu-control-p1-05-recovery` at
`c824b9018ea9dfd3d9f8b45f65b7b3fd60c4fb01` and created Draft PR #52
(`main` → P1 candidate, 40 files). PR #51 was retargeted to use the P1
candidate as its base; it remains a broad 163-file Draft follow-up and should
not be merged alongside #52 as-is. At the latest check refresh, #52's seven
required Actions checks were pending while Vercel had passed. #51's old
main-based checks do not validate its new base. No GitHub reviews have been
submitted. Local P1 suites and the user-selected Security Review passed as
documented above; these do not replace remote CI/review or runtime acceptance.
The exact-source replay patch is refreshed at
`/tmp/gpu-control-main-full-current-20261031-final20.patch` after this note.

## Current continuation refresh — 2026-10-31

- HEAD remains `a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits ahead
  of `origin/main`; it diverges from the pushed PR #51 branch (55 ahead / 56
  behind). The worktree has 45 modified tracked and 16 untracked paths (61
  total), all unstaged. Its ownership table in
  `2026-10-28-gpu-control-worktree-slices.md` matches the live Git path set
  exactly (61/61, no missing, stale, or duplicate entries).
- Current PR #52 and stacked PRs #57–#59 remain OPEN/DRAFT with seven required
  Actions checks and Vercel passing on each current head, but no submitted
  GitHub reviews. #52 remains `REVIEW_REQUIRED`. Local suites do not cover
  these 61 paths.
- A fresh GitHub protection read confirms the seven required checks, one
  approval with last-push approval, strict history, conversation resolution,
  linear history, and admin enforcement. Production/Preview Environments have
  no required reviewers or deployment-branch restrictions. The parked machine
  policy lists those three controls as normative paid-activation prerequisites;
  repository search found no runtime reader that verifies live GitHub settings.
  Any future activation/issuer path must consume fresh trusted API evidence and
  fail closed. Focused policy/context tests pass 14/14. No external settings
  changed.
- Fresh production alias GETs at 2026-10-30 21:59 UTC returned `/healthz`=200,
  `/readyz`=404, OAuth discovery=200, and unauthenticated `/mcp`=401. The
  Gateway is not runtime-ready for ChatGPT acceptance. The browser session
  remains logged out; real OAuth/tool/CPU/result acceptance remains unverified.
- Preserve `policies/repository-state.yaml` at `mode: parked`. Continue
  candidate reconciliation and local validation while independent PR review,
  authenticated ChatGPT access, and deployment/runtime acceptance are pending.

## P1 readiness integration candidate refresh — 2026-10-31

- Published PR #52 and #57–#59 currently have all seven required Actions
  checks and Vercel passing, but remain Draft; #52 is `REVIEW_REQUIRED` and
  #57 has no submitted review. Green checks cover their published heads only.
- The new isolated P1 candidate combines the local CPU `/readyz` admission
  gate with PR #58's OAuth DCR/schema-v9 head
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4`. Patch:
  `/tmp/gpu-control-p1-readiness-on-58.patch`, SHA-256
  `8437253e113d0bf8f81fc3a27721b0157c02f5ddfef7aa081646fe1933fb6918`.
  It updates two existing readiness test fixtures to prove a valid allowlisted
  CPU policy and exact source identity; the fail-closed code path stays enabled.
- Full Gateway suite on that candidate: **418 passed, 13 skipped** (optional
  Torch/Modal, Docker CPU smoke image, and PostgreSQL services unavailable).
  Candidate imports resolved to the isolated worktree and `git diff --check`
  passed. A read-only Security Review of this exact #58 overlay found no issues
  in its three changed files; the candidate base and patch SHA were rechecked
  after review. It still needs CI on a published head and a GitHub review.
- Continue from this exact candidate for review preparation. Do not treat the
  green CI on PR #58 as covering it. Preserve dirty primary checkout, Draft PR
  state, and `policies/repository-state.yaml mode: parked`; no deployment,
  OAuth grant, or provider call was made.

## P1/P2/P3 candidate composition refresh — 2026-10-31

- Current remote chain is #52 → #53 → #54 → #55 → #56 → #57 → #51 → #58;
  P3 PR #59 is a sibling off #57. The P2 and P1 lifecycle PR heads #53–#57
  are ancestors of #58, so #58 already contains those revisions.
- PR #59's direct patch is not a valid rebase input for #58: of its 14 paths,
  12 differ on #58 and two are identical. Do not apply the branch wholesale.
- A source-owned P3 operations slice applies after the P1 readiness overlay on
  exact PR #58 head `561a6c7`. Use the complete 14-path candidate at
  `/tmp/gpu-control-p1-p3-on-58-complete.patch`, SHA-256
  `5c0acf229ccc0f07a32155ab5498c4685a8c9791c1a31fc4f5d7848b144319b8`.
  The earlier export omitted four untracked P3 test/evidence files and is
  superseded. The complete patch replayed to 328 matching paths on a second
  fresh #58 worktree. Full Gateway suite: **420 passed, 14 skipped**;
  PostgreSQL test services and CPU Docker image were not configured. The
  PostgreSQL integrity test later passed 1/1 against the candidate.
  Details: `docs/acceptance/2026-10-31-p1-p3-integration-on-58.md`.
- Follow-up PostgreSQL-backed artifact-manifest regression on this same
  candidate passed **1/1** against pinned PostgreSQL 16 bound to loopback. The
  task-created DB container was stopped and verified absent. This does not
  replace a full DB-backed suite or target-host restore/operations acceptance.
- A separate read-only Security Review of the complete staged 14-path P1+P3
  candidate found no actionable issues, including its added P3 evidence and
  PostgreSQL test. It still needs CI on a published head and a GitHub PR
  review. No GitHub write or deployment occurred. Keep `mode: parked` and all
  provider/spend gates closed.
- On this exact candidate, the real local CPU MCP integration passed **1/1**
  with the cached digest-pinned image after setting its matching OCI source
  revision. It verified idempotent prepare, submit, real Docker execution,
  result and artifact retrieval through a second client, and cleanup. Run
  `675d173fdce540668667bd740c126bfa` ended succeeded/cleaned with artifact SHA
  `2a72f26082461ba058e4773c6f481f4573f369e9c01903f5d73055d3908c4819`. This
  used synthetic OAuth/in-process MCP and is not ChatGPT or hosted acceptance.
- The exact candidate's eight systemd service/timer units also passed
  `systemd-analyze verify` in network-isolated Debian 12/systemd 252.39 with
  read-only source mount and inert placeholders. No services started. Target
  host boot/mount/restart/readiness and alert delivery remain unverified.

## P3 systemd and live production refresh — 2026-10-31

- The exact #58 candidate's eight service/timer units pass `systemd-analyze
  verify` on a network-isolated Debian 12/systemd 252.39 container using a
  read-only deployment mount and inert placeholders. No service ran; this does
  not cover target-host behavior.
- Fresh unauthenticated production checks: `/healthz`=200, `/readyz`=404,
  OAuth authorization-server metadata=200, `/mcp`=401. Current P1 readiness is
  not deployed.
- PR #58 remains Draft at `561a6c7`; its seven required CI checks and Vercel
  pass on the published head, no review is submitted, and it does not include
  `/tmp/gpu-control-p1-p3-on-58-complete.patch`. ChatGPT acceptance, selected
  P3 host/region/budget/origin/alert/SLO and target-host recovery remain open.
