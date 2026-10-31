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

## P0: 現行基準を揃える（1〜2 PR）

- [ ] mainとPR #43の正確なSHAを取得。各監査修正を「mainに存在／未適用／後続で置換／要調査」に分類する。
- [ ] `docs/BASELINE_AUDIT.md`に対象ファイル、根拠、再現テスト、適用順序を記録する。PR全体を無条件にcherry-pickしない。
- [ ] README/STATUS/実コードの相違を修正し、Gatewayとcoreの責務を記録する。
- [ ] 利用予定ChatGPTアカウントでcustom MCP接続が利用可能か確認する。HTTPS endpoint、OAuth、永続DB、常時workerの既存構成を調査し、不足を具体名で記録する。
- [ ] PR #43のCPU/MCP公開にも関係する修正を小さいPRで取り込む。RunPod固有の残項目はP5の必須ゲートとして追跡する。

完了条件: 採用基準SHA、差分表、接続条件、最初のCPU workloadが確定。接続権限がなければMCP_CONNECTIVITYをBLOCKEDと記録し、backend実装まで進める。

## P1: ChatGPTから実CPUジョブを使う（7タスク、4〜7 PR）

詳細は `2026-10-28-gpu-control-first-vertical.md`。

- [ ] 現行DBから移行可能なversioned plan・状態・結果契約を導入する。
- [ ] `experiment_capabilities / prepare / submit / status / result / cancel / list`を公開する。
- [ ] trusted registryのCPU workloadを0ドルでprepareできるようにする。低リスクの事前運用許可を厳密に限定し、有償承認は維持する。
- [ ] 既存project_controlの検証・隔離を再利用するlocal Docker CPU backendを独立workerへ接続する。
- [ ] process/containerの実行証拠、source SHA、image digest、fingerprint、metrics、cleanupを返す。
- [ ] 同じkeyの再送、再実験の新key、owner別検索、worker再起動、cancelを実containerで確認する。
- [ ] 実ChatGPTで初回接続・実行・別会話での検索・結果取得を行う。

最初のworkloadは標準ライブラリだけの決定的 `cpu-smoke-v1`。次に既存 `orbitune-tokenizer`を接続する。GPU必須入力にCPUを自動実行しない。CPUが許可された要求のみ0ドル経路を使う。

完了条件: 別ChatGPT会話からコード/CLI操作なしで実CPUのrun_id・結果を取得できる。実行中worker再起動とcancelの証拠があり、simulation=false / gpu_used=falseを返す。

## P2: 障害時にも取りこぼさない（3〜5 PR）

主な変更先: `worker.py`, `store.py`, 新規 `lifecycle.py`, `supervisor.py`, `artifacts.py`, `gateway/tests/`。

- [ ] allocation前のintentをDBに永続化し、provider/owner/run/attempt/planを結びつける。API再送・worker lease更新・再照合の責任を明記する。
- [ ] 実行状態とcleanup状態を分離する。プロセス終了後もcleanup未確認なら資源枠を解放しない。cleanup失敗で結果を消さない。
- [ ] 独立supervisorがtimeout、cancel、worker heartbeat切れ、cleanup_pendingを処理する。DB/worker停止中も効く実行期限を各backendに設ける。
- [ ] create直後、handle保存直前、結果保存直後、cleanup直前に停止するfault injection試験を作る。DB一時停止、二重worker、遅いprovider、lease期限超過を含む。
- [ ] unknownを再submitせず、完全に識別できる既存資源へ再接続する。不在が証明できない場合はUNKNOWNを保持する。
- [ ] 小さい結果JSONはDB、ファイル成果物はowner管理の保存先へ分離。最初の上限案は1 runあたり10 MiB、JSON/ログ各64 KiB。巨大checkpointは未対応と返す。
- [ ] artifactはdigest/size/media type/expiryを記録。任意pathやURLを直接読む機能を作らず、期限付き取得はowner照合後だけ許可する。

完了条件: 指定した各停止点で資源重複0件、他runの削除0件、既存結果消失0件。成功・失敗・cancelのすべてでcleanupの証拠が取れる。provider完全障害時はUNKNOWNと最後の観測時刻を正しく返す。

## P3: 放置しても運用できるCPU安定版（3〜4 PR）

主な変更先: `gateway/docker-compose.yml`, deploy設定、DB migration、`docs/OPERATIONS.md`, `docs/CHATGPT_ACCEPTANCE.md`。

- [ ] 本番Gatewayと独立workerの構成を1つ選び、TLS、永続PostgreSQL、migration、worker自動再起動を整える。APIにDocker socketやprovider secretsを渡さない。
- [ ] OAuth接続/refresh/revocation、誤audience、誤scope、PKCE、redirect URI、CSRF、rate limit、owner境界を検証する。
- [ ] 内蔵OAuthのissuerがURL変更で変わる点を扱う。ドメイン変更で別ownerになった既存runを自動公開せず、明示的移行を用意する。
- [ ] DB backup/restoreを実行し、run・approval・OAuth状態の復旧を確認。成果物も対応する世代へ復元できるようにする。
- [ ] readinessはDB、migration version、worker heartbeat、registry有効性を確認する。liveness成功を計算可能の証拠にしない。
- [ ] 7日間の少数・非課金試験で接続切れ、再起動、停止、日をまたぐ検索を観察する。監視で実験を勝手に再実行しない。

目標: 通常負荷でstatus応答p95 2秒以内、submit応答5秒以内、local cancelから解放30秒以内。環境・サンプル数・負荷条件を証拠に含め、未測定をPASSにしない。DB backupは当初RPO 24時間/RTO 2時間を目標とし、受理済みjob自体はDB commit後にのみ応答する。

完了条件: ownerが日常利用でき、再起動/バックアップ復元手順を別担当者が再現できる。CPU版としてリリース可能。有償GPU完成を待たせない。

## P4: 最小コストの資源選択と実GPU（3〜6 PR）

主な変更先: 新規 `capabilities.py`, `selection.py`, `costs.py`, `workloads.py`、既存Modal backend、対応tests/docs。

- [ ] provider単位ではなくworkload実行可能性を判定する。GPU/VRAM、OS/architecture、依存環境、timeout、待ち時間、結果回収、cleanup、費用証拠の有効期限を入力にする。
- [ ] `LOCAL / FREE / FREE_QUOTA / CREDIT_BACKED / PAID / MANUAL_ONLY / UNSUPPORTED / UNKNOWN`を公開し、availabilityと費用分類を別々に保持する。
- [ ] まず既存Modal adapterの公式APIを再検証し、利用者アカウントの実際のquota/credit/支払い制御を確認する。実行可能性がなければ理由を記録して他候補1つを調査する。
- [ ] FREE_FIRSTは適合候補を絞り、証明済みの追加料金0枠を優先する。credit残高だけでゼロ課金を保証しない。overageを確実に止められない枠は0ドル要求でBLOCKEDにする。
- [ ] GPU候補の不在では `FREE_GPU_UNAVAILABLE`、quota不明では `QUOTA_UNKNOWN` を返し、CPU代案と有償prepareを案内する。
- [ ] GPU smokeは実デバイス情報と小さいCUDA演算を含め、device名、VRAM、provider handleに対応する証拠、exit、時間、使用量、cleanupを記録する。
- [ ] quotaの競合消費・見積り失効をsubmit/worker直前に再評価し、planを勝手に別providerへ変更しない。

候補扱い: local CUDA/ROCmは実ハードウェアがある場合のみ。MacのMetal/MPSはCUDA成功として扱わない。Kaggle、Hugging Face/ZeroGPU、user-operated Colab、GitHub Actions CPUは公式の実行・回収・停止APIと規約を検証してから採用。現時点で無料・無人運用可能とは認定しない。

完了条件: 最低1つの実GPU backendでGPU実測、復旧、cancel、費用/cleanupが確認済み。無料条件が成立しなければFREE_GPU_EXECUTIONはBLOCKEDのままCPU版を維持する。

## P5: RunPodの有償実行（3〜5 PR）

主な変更先: `src/gpu_control/human_authorization.py`, `providers/`、新規Gateway core bridge、activation docs/policies。

- [ ] PR #43由来のallocation直前期限再確認、HTTP境界、receiptに結びついたrecovery-onlyを現行main上で検証する。
- [ ] Gateway planとcore ApprovedExecutionPlan/LiveExecutionPermitの変換を定義。browser承認はtrusted server側でexact plan・期限・owner・control-plane SHAへ結びつける。
- [ ] 保護main、必須checks、必要なEnvironment/権限、immutable image、現在の価格/在庫、Network Volume/S3 transportを確認する。
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
