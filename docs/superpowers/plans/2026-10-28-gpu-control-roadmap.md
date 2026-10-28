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

## Review Focus

1. 同じsubmitを通信再試行した場合と「もう一度実験して」を区別し、前者は同一run、後者は新runにする（P1/T3、P2）。
2. provider作成直後のworker停止、DB停止、lease競合で二重作成・無関係な資源削除をしない（P1/T5、P2）。
3. OAuth期限切れ、issuer変更、別会話・別利用者からの参照で所有権が変わらない（P1/T6、P3）。
4. 無料quotaの競合消費、期限切れ見積り、計算終了後のストレージ料金でゼロ費用を偽らない（P4、P5）。
5. 不正・巨大・欠落した結果、モデル出力に含まれる命令で制御操作や成功判定が変わらない（P1/T4、P2、P6）。

## 2026-10-28の確認済み基準

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
| main branch API | protected=false | 有償公開前の運用条件。今回未変更 |

PR #43の説明にはHTTP/期限/復旧/配布物の修正とCI結果がある。ただし本計画ではCIを再実行していない。PR本文の過去の成功を現在mainの受入証拠にしない。READMEには古いSHA・transport説明が残り、`docs/STATUS.md`や実装と不整合がある。

このフォルダはGit checkoutではなく計画書の保存場所。実装担当は本体を取得し、これらの文書を本体へ取り込む。今回アプリ実装、環境変更、課金実行は行っていない。

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

この計画は長期目標を示す。以下の現状スナップショットと未解決ゲートを更新してからLunaへ渡し、各段階の受入条件を満たす順に実装する。

- GitHub `main`: `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`。Draft PR #51 `codex/chatgpt-cpu-vertical` はhead `c1541a829825ef627cddd86cb81efd36a2d2ed5a`、120 files、4 GitHub Actions checks success、Vercel preview success、reviewは未着。PR #43は別のDraft監査PRとして存在する。
- ローカル証拠: P1のT1-T5 CPU lifecycleとHTTP/MCPを通した実Docker実行、P2のrecovery/paired backup restore、およびP4のoffline capability/selection契約が実装・限定scopeで検証済み。これらは実ChatGPT受入、production復旧、GPU実行を意味しない。
- 公開先: Vercel `gpu-control` の最新READY production buildは上記main SHAのまま。2026-10-28の公開alias確認は `/healthz=200`, `/readyz=404`, 未認証`/mcp=401`。P1実装は未公開。Vercel projectのroot外source include設定と実buildも未確認。
- 運用先: P3 decisionは専用Linux + systemd API/worker/recovery + managed Neon + 固定artifact filesystem + TLS proxy。ホスト/provider、region、公開HTTPS origin、月額cost ceilingは未決であり、購入・本番変更は未承認。Neon production schemaは未移行で、既存OAuth admin/session stateを保全する必要がある。
- 安全ゲート: `policies/repository-state.yaml` は `mode: parked`。有償compute、RunPod live call/adapter/workflow、一般外部container実行は無効のまま維持する。コード変更・dry run・repository accessはactivation承認ではない。

直近の順序:

1. **PR #51の独立レビューとCI follow-upを得る。** 現在のActions/preview checksはsuccessだがreviewは未着。PR #43との差分を再照合し続け、指摘があればhead SHAを固定して対応・再CIする。mainへの直接反映、merge、parked解除を含めない。
2. **実ChatGPT接続条件を確認する。** 利用者が使うworkspaceでcustom MCP write actionsが可能か、OAuth app接続・tool discovery・tool callを確認する。権限やworkspace設定が揃わなければ具体的なBLOCKED条件を記録し、独立してできる実装を進める。
3. **P3 host choiceを閉じる。** 月額上限、region、host/provider、public HTTPS originを確定してから運用構成をdeploy可能なrunbookにする。ホスト購入やproduction変更は明示承認後のみ。
4. **隔離先でproduction形状の導入を検証する。** migration、Neon互換backup/restore、artifact volume、service restart/mount/permission、TLS/proxy、monitor/alertを実測し、既存OAuthとowner境界を確認する。production schema変更は別途レビューと承認後。
5. **レビュー・CI後に実CPU verticalをdeployしChatGPT acceptanceを実施する。** 別ChatGPT会話でprepare/submit/status/result/search/artifact/cancel、worker restart、owner isolationを記録する。実ChatGPT・実ホスト証拠が揃うまで各軸をUNCERTAIN/BLOCKEDに保つ。
6. **P3の安定運用期間を測る。** seven-day observation、target-host cancellation/recovery、second-operator restore、measured RPO/RTO、capacity alert deliveryを完了する。
7. **その後P4→P5→P6→P7へ進む。** 最初の実GPU backendを選ぶ際に現行provider/API/規約/quota/pricingを再確認し、free GPUとpaid GPUは別release axisとする。P5 paid executionは別の明示authorizationを要する。

### 現在の未コミット差分を分けるレビュー単位

現worktreeは67 tracked pathsの変更と28 untracked pathsを含む（2026-10-28のporcelain status集計）。現時点でPR/commitへ分割済みではない。いずれも現行CIと個別レビューを通すまでproduction受入に使わない。

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
- [ ] 利用予定ChatGPT workspaceでcustom MCPのwrite actionsが利用可能か確認する。Business/Enterprise/Eduのweb workspace、作成・試験者の権限、`Create plugins with MCPs`およびwrite action設定を記録する。Proのread/fetch-only接続はrun/cancel受入条件を満たさない。詳細は[OpenAIの接続要件](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)を参照する。HTTPS endpoint、OAuth、永続DB、常時workerの既存構成も調査し、不足を具体名で記録する。
- [x] PR #43からCPU/MCP公開にも関係するHTTP境界・dependency修正を選択的にローカル実装し、回帰根拠を記録した。これはPR #43のmerge/cherry-pickやlive provider acceptanceを意味しない。RunPod固有の残項目はP5で追跡する。
- [ ] 実装差分を独立レビューできる小さいPRにまとめ、現在のGitHub `main`をbaseにレビューと最新CIを得る。現状の変更はローカル未コミットで、この作業ブランチはGitHubにpushされていない。

完了条件: 採用基準SHA、差分表、接続条件、最初のCPU workloadが確定。接続権限がなければMCP_CONNECTIVITYをBLOCKEDと記録し、backend実装まで進める。

## P1: ChatGPTから実CPUジョブを使う（7タスク、4〜7 PR）

詳細は `2026-10-28-gpu-control-first-vertical.md`。

- [x] 現行DBから移行可能なversioned plan・状態・結果契約を導入する。
- [x] `experiment_capabilities / prepare / submit / status / result / cancel / list`を公開する。
- [x] trusted registryのCPU workloadを0ドルでprepareできるようにする。低リスクの事前運用許可を厳密に限定し、有償承認は維持する。
- [x] 既存project_controlの検証・隔離を再利用するlocal Docker CPU backendを独立workerへ接続する。
- [x] process/containerの実行証拠、source SHA、image digest、fingerprint、metrics、cleanupを返す。
- [x] 同じkeyの再送、再実験の新key、owner別検索、worker再起動、cancelを実containerで確認する。
- [ ] 実ChatGPTで初回接続・実行・別会話での検索・結果取得を行う。
  - Local OAuth now advertises RFC 7009 revocation and binds refresh/access credentials to a persisted grant family; a v6-to-v7 additive migration preserves existing tokens. This is local protocol evidence only and does not establish live ChatGPT acceptance.

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
  - 2026-10-28 read-only provider shortlist: Lightsail offers Tokyo and Singapore. A 2 GB VM plus a 32 GB separate artifact disk is currently estimated at $15.20/month; 4 GB plus that disk at $27.20/month, before snapshots, transfer overage, tax, domain, or backup costs. Singapore is the first region to measure against the existing Singapore Neon database; Tokyo remains an alternative. DigitalOcean is a Singapore-only comparison for this shortlist and lacks a currently listed Japan datacenter. These are candidate prices, not a selected provider or approved budget. The owner-set cost ceiling, exact region, and account-specific availability are still open. See the linked topology decision for official price sources and limits.
  - Added `gpu-control-db-migrate.service` as a manually started, hardened oneshot with no boot-install target. Production use remains gated on quiescence, paired backup/restore, and review of the exact release migration.
  - 2026-10-28 read-only Neon inventory found an existing unversioned v1 Gateway schema, zero runs/active slots, and existing local OAuth admin/session state. The initial isolated v1-to-v6 `Store.initialize()` rehearsal is historical; after schema v7, the current operator `--init-db` entrypoint was rerun twice against an isolated v1-shaped PostgreSQL 16 database and preserved synthetic run/OAuth rows, with unknown future schema rejected without mutation. This does not authorize or validate production migration; see `docs/acceptance/2026-10-28-neon-first-schema-migration.md`.
  - 現行Vercel Functions案は `gateway/vercel.json` の `maxDuration: 30` で、queueを常時監視するworkerには使わない。Vercel Sandboxは別製品で、現行公式資料ではPro/Enterpriseのsession上限が最大24時間、snapshotとDriveによる永続化がある。P3の構成選定時に候補比較はできるが、利用可能なplan、請求/上限、停止後の再開・queue監視、専用workerの信頼境界、DB/成果物の永続性を実環境で確認するまでは採用済みと扱わない。
  - Local Vercel package preflight builds a Gateway wheel from valid PEP 621 metadata and checks the runtime dependency list against `requirements.txt`. A Vercel preview for PR #51 built exact head `c1541a8` to READY, confirming that the shared root `gpu-control` package resolved for that build. The explicit include-outside-Root-Directory project setting was not directly read; recheck it after changing Vercel build configuration.
  - 比較対象は専用Linux host (systemd)、Vercel Sandbox + Drive、および必要なら既存のmanaged PostgreSQL/storage。選択理由、費用上限、failure/recovery実測を記録する。いずれもCPU policy enableより前に同じacceptance gateを通す。
- [ ] OAuth接続/refresh/revocation、誤audience、誤scope、PKCE、redirect URI、CSRF、rate limit、owner境界を検証する。
  - 2026-10-28 offline regression fixed a rollback bug in the built-in OAuth failed-login counter; the fifth invalid password now activates a persisted lockout and expiry is verified. The complete item stays open until live ChatGPT/OIDC and all listed protocol/owner cases pass. See `docs/IMPLEMENTATION_PROGRESS.md`.
- [x] 内蔵OAuthのissuer変更用オフライン移行手段を実装し、実DB複製とartifact fixtureでローカル検証した。移行元/先issuer・subjectの明示確認、quiescence、衝突・digest検査、再開可能なコピー/rollback手順、旧token/session失効、owner境界を検査する。実装とSIGKILL試験の範囲は`docs/acceptance/2026-10-28-owner-issuer-migration.md`を参照する。これはproduction migrationの承認や実行ではない。
  - Production rollout remains separate: stop all services/admission, take and verify a paired production backup, run read-only preflight, independently review the exact migration, apply it, then verify owner counts, artifact digests, old-issuer rejection, and cross-owner denial before resuming.
  - 移行元と移行先issuer/subjectを明示し、認証済みの同一ownerであることをoperatorが確認してから実行する。subだけの一致や新issuerへのログインだけでは移行を許可しない。
  - API、worker、supervisorを停止し、新しいsubmitを遮断した状態でDBとartifact volumeを同じ世代として退避する。通常のAPIリクエストや起動時migrationでownerを自動書換えしない。
  - runのowner、submission intent内のowner参照、artifact scope directoryをまとめて移行する。現行schemaに独立approval tableやplan内owner参照はない。owner/idempotency一意制約の衝突・対象件数・参照整合性を検査し、artifactを新scopeへコピーしてmanifestのsize/SHA-256を照合する。原本を保持し、DB更新とartifact切替の不一致から再実行・復旧できる段階設計にする。
  - 旧issuerのtoken/sessionを引き継がず、旧URLの認証を拒否する。移行後は新issuerでrun一覧、status、result、artifactの読出しを確認し、別ownerからの全経路が404/拒否となること、件数・owner境界・成果物digestが一致することを証拠に残す。
  - 実DB複製と実artifact fixtureで、成功移行、同一owner再実行、衝突時の無変更、途中失敗後の復旧、別owner拒否を検証する。通常運用への復帰は全検査成功後のみ許可する。
- [x] Paired DB/artifact backup generation and isolated restoreを実装・ローカルsynthetic PostgreSQL 16で実行し、run/OAuth stateとowner-scoped artifact retrievalを確認した。v7 refreshではOAuth `grant_id`/revocation状態も確認し、PostgreSQL 16 generationを別PostgreSQL 17.11 DBへrestoreしてschema/run/artifact/OAuthの保持を確認した。手順と限界は`docs/acceptance/2026-10-28-paired-artifact-restore.md`および`docs/acceptance/2026-10-28-atomic-backup-generation.md`に記録した。
  - [ ] Neon固有のpaired backup/restore挙動とsecond-operator手順を、承認済みの隔離環境で確認する。
  - [ ] 選定production database/artifact volumeでpaired backup/restoreを行い、second-operator手順とRPO/RTO実測を記録する。
- [x] `/readyz`はDB、schema migration version、worker/supervisor heartbeat、registry有効性を検証し、境界テストを持つ。コード上の実装証拠は`gateway/gpu_gateway/health.py`、`gateway/tests/test_health.py`、`gateway/tests/test_http_auth.py`。
  - [ ] 選定ホストに配置し、実サービス再起動・DB停止・stale heartbeat時にreadinessと回復動作を受け入れ確認する。
- [x] Local CPU artifact admissionのfilesystem/headroom probeはcapabilities、prepare、worker直前でfail-closedし、systemd monitorも実装済み。ローカルfixture evidenceは`docs/acceptance/2026-10-28-artifact-storage.md`。
  - [ ] 選定ホストでfixed-size filesystem quota、alert通知/復旧通知、quota上限時のwrite失敗・cleanup、API/worker/supervisor継続稼働を実測する。`statvfs`だけをquotaや通知の証拠にしない。
- [ ] `docs/CHATGPT_ACCEPTANCE.md`のSeven-day CPU operations observationに従い、接続切れ、worker再起動、停止、日をまたぐ検索を7日間記録する。現在はNOT STARTED。監視で実験を勝手に再実行しない。

目標: 通常負荷でstatus応答p95 2秒以内、submit応答5秒以内、local cancelから解放30秒以内。環境・サンプル数・負荷条件を証拠に含め、未測定をPASSにしない。DB backupは当初RPO 24時間/RTO 2時間を目標とし、受理済みjob自体はDB commit後にのみ応答する。

完了条件: ownerが日常利用でき、再起動/バックアップ復元手順を別担当者が再現できる。CPU版としてリリース可能。有償GPU完成を待たせない。

## P4: 最小コストの資源選択と実GPU（3〜6 PR）

主な変更先: 新規 `capabilities.py`, `selection.py`, `costs.py`, `workloads.py`、既存Modal backend、対応tests/docs。

Implementation brief: [`docs/specs/p4-capability-selection-contract.md`](../../specs/p4-capability-selection-contract.md)。既存`PricingVerificationResult`と`ApprovedExecutionPlan`の境界を維持し、discovery/selectionでhuman authorizationやprovider submitを発生させない。

- [ ] provider単位ではなくworkload実行可能性を判定する。GPU/VRAM、OS/architecture、依存環境、timeout、待ち時間、結果回収、cleanup、費用証拠の有効期限を入力にする。
  - 2026-10-28 offline implementation: `src/gpu_control/workloads.py`, `capabilities.py`, `selection.py` define immutable workload requirements, independent availability/cost evidence, per-run cost components, freshness checks, deterministic compatibility filtering, `FREE_FIRST`, and refusal reasons. Gateway now accepts explicit optional P4 requirements in its operator manifest and invokes the selector read-only; absent provider inventory fails closed as `PROVIDER_EVIDENCE_UNAVAILABLE`. Local root/Gateway suites: 517/262 passed (1/8 skipped); Docker API/worker image builds and shared-package imports passed. The GPU example declares execution requirements but leaves exact source repository/SHA blank, with regression coverage that selection remains blocked until they are supplied. No provider/account/live GPU evidence is implied; Vercel deployment packaging remains unverified. Details: `docs/specs/p4-capability-selection-contract.md`.
- [ ] `LOCAL / FREE / FREE_QUOTA / CREDIT_BACKED / PAID / MANUAL_ONLY / UNSUPPORTED / UNKNOWN`を公開し、availabilityと費用分類を別々に保持する。
- [ ] まず既存Modal adapterの公式APIを再検証し、利用者アカウントの実際のquota/credit/支払い制御を確認する。実行可能性がなければ理由を記録して他候補1つを調査する。
  - 2026-10-28: Modal Sandboxの公式timeout/idle-timeout/termination仕様と公開pricingを現行adapterと照合した。worker専用adapterは固定argv・prebuilt image・GPU/CPU/RAM/runtime・block_network・cancel/reconcileの境界を持つが、ユーザーworkspaceのplan/quota/credits/budget/overageは未確認。公開価格のincluded creditはzero-additional-cost保証ではない。Modal readiness記録: `docs/decisions/2026-10-28-p4-modal-readiness.md`。このP4 itemはアカウント確認が残るため未完了。
- [ ] FREE_FIRSTは適合候補を絞り、証明済みの追加料金0枠を優先する。credit残高だけでゼロ課金を保証しない。overageを確実に止められない枠は0ドル要求でBLOCKEDにする。
- [ ] GPU候補の不在では `FREE_GPU_UNAVAILABLE`、quota不明では `QUOTA_UNKNOWN` を返し、CPU代案と有償prepareを案内する。
- [ ] GPU smokeは実デバイス情報と小さいCUDA演算を含め、device名、VRAM、provider handleに対応する証拠、exit、時間、使用量、cleanupを記録する。
- [ ] quotaの競合消費・見積り失効をsubmit/worker直前に再評価し、planを勝手に別providerへ変更しない。

候補扱い: local CUDA/ROCmは実ハードウェアがある場合のみ。MacのMetal/MPSはCUDA成功として扱わない。Kaggle、Hugging Face/ZeroGPU、user-operated Colab、GitHub Actions CPUは公式の実行・回収・停止APIと規約を検証してから採用。現時点で無料・無人運用可能とは認定しない。

完了条件: 最低1つの実GPU backendでGPU実測、復旧、cancel、費用/cleanupが確認済み。無料条件が成立しなければFREE_GPU_EXECUTIONはBLOCKEDのままCPU版を維持する。

## P5: RunPodの有償実行（3〜5 PR）

主な変更先: `src/gpu_control/human_authorization.py`, `providers/`、新規Gateway core bridge、activation docs/policies。

- [ ] PR #43由来のallocation直前期限再確認、HTTP境界、receiptに結びついたrecovery-onlyを現行main上で検証する。
  - Offline hardening added: RunPod REST v1/v2, pricing GraphQL, and S3 reads now reject redirects and cap response bodies. Both adapters revalidate the live permit, exact price evidence freshness, and pre-create occupancy at one timestamp immediately before the create call. Injected-clock tests prove expired evidence prevents allocation; this does not verify live provider compatibility or the remaining receipt/recovery-only behavior.
- [ ] Gateway planとcore ApprovedExecutionPlan/LiveExecutionPermitの変換を定義。browser承認はtrusted server側でexact plan・期限・owner・control-plane SHAへ結びつける。
- [ ] 保護main、必須checks、必要なEnvironment/権限、immutable image、現在の価格/在庫、Network Volume/S3 transportを確認する。
- [ ] 同一アカウントの並行submitを安全に直列化する。現在の短命occupancy snapshotの再確認だけでは別プロセス間の競合を防げないため、account-wide lock/leaseまたはprovider-enforced idempotencyを実装し、競合canaryで重複allocationが0件である証拠を得る。
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
