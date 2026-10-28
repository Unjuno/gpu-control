## 1. 〈本論〉

そうです。前のゴール設定は少し広げすぎました。

あなたが作りたいものは、**GPUクラウドの汎用CLIそのものではなく、ChatGPTの通常のチャットから「この実験をやって」と言えば、`gpu-control` がツールとして呼び出され、適切な計算資源で実験して結果がその会話へ返る仕組み**です。

最終形はこれです。

```text
ChatGPT Chat
    ↓ tool call / MCP
gpu-control Gateway
    ↓
prepare / quote / approval
    ↓
durable job queue
    ↓
worker
    ↓
Local / GitHub CPU / Modal / Kaggle / RunPod / etc.
    ↓
result + metrics + artifacts
    ↓
gpu-control Gateway
    ↓
ChatGPT Chat
```

つまり、ユーザー体験としては例えば、

> 「Orbituneのこのcommitで、小さい学習実験をして。まず無料GPUを使って、無理なら理由を教えて」

とチャットするだけでよい状態がゴールです。

既存リポジトリはこの方向にかなり近いです。`gateway/` にはすでにRemote MCP、永続キュー、承認、worker、Modal backend、RunPod bridgeという骨格があります。したがって**ここから新しい巨大なシステムを作るのではなく、ChatGPTから安定して呼べるMCP製品として完成させる**のが正しい方針です。

Codexへ渡すゴールプロンプトも、こちらへ変更してください。

# Codexへの開発指令 — ChatGPT-native Experiment Control Plane

## 最終目標

対象：

`Unjuno/gpu-control`

このプロジェクトの最終目的は、CLI中心のGPU管理ツールを作ることではない。

**ChatGPTの通常のチャットから、自然言語で実験を依頼すると、ChatGPTが `gpu-control` をツールとして呼び出し、実験を準備・実行・監視・回収し、その結果を同じ会話へ返せる状態を完成させること。**

最終的なユーザー体験は次である。

```text
User
「このGitHub commitで、小さいGPU実験をして。
まず無料資源を使って、なければ実行前に教えて」
        ↓
ChatGPT
        ↓ MCP/tool call
gpu-control
        ↓
plan → resource selection → approval → execution
        ↓
worker / provider
        ↓
result
        ↓
ChatGPT
「実験完了。GPU=X、実行時間=Y、結果=Z」
```

ユーザーが通常操作で provider API、Docker、workflow、CLIを直接扱う必要がないことを完成条件とする。

---

## 1. ChatGPTを正式なフロントエンドとする

既存 `gateway/` のRemote MCP実装を中心にする。

Web UIやCLIは運用・デバッグ・管理用として残してよいが、主要な製品経路は：

```text
ChatGPT
 -> authenticated Remote MCP
 -> gpu-control gateway
 -> durable queue
 -> independent worker
 -> provider
```

とする。

ChatGPT側から必要な操作がすべてtool callとして行えるようにする。

---

## 2. ChatGPTへ公開するMCPツール

ツール数をむやみに増やさない。

最低限、以下の意味論を提供する。

### `experiment_capabilities`

目的：
現在利用可能な実験環境を確認する。

返却：

- provider
- CPU/GPU
- GPU種類
- VRAM
- workload形式
- availability
- free/paid区分
- quotaの既知情報
- 現在実行可能か
- 人間承認が必要か

これはread-onlyである。

---

### `experiment_prepare`

目的：
自然言語要求から、実行可能な具体的実験planを準備する。

入力例：

```json
{
  "repository": "owner/repo",
  "commit": "<40 hex sha>",
  "workload": "registered-workload",
  "parameters": {},
  "runtime_seconds": 300,
  "max_cost_usd": "0.00",
  "resource_policy": "free_first"
}
```

返却：

- exact source identity
- workload
- provider candidate
- CPU/GPU
- runtime
- estimated cost
- free quota classification
- plan fingerprint
- approval requirement
- blockers

`prepare` は資源を作成しない。

---

### `experiment_submit`

目的：
承認された正確なplanを実行する。

重要：

**ツール引数の `approved=true` のような値を、人間の承認として扱わない。**

有償処理や高影響処理については、既存のbrowser approvalまたは信頼できるstructured authorizationとexact fingerprintを使用する。

無料の低リスク実行についても、provider規約と利用者authorityの範囲内だけで実行する。

返却：

```json
{
  "run_id": "...",
  "state": "queued",
  "provider": "...",
  "plan_fingerprint": "..."
}
```

長時間処理中にMCPリクエストを保持し続けない。

---

### `experiment_status`

目的：
ジョブ状態をChatGPTから確認する。

返却：

- queued
- preparing
- running
- succeeded
- failed
- cancelling
- cancelled
- cleanup_pending
- cleanup_complete
- unknown

さらに：

- elapsed time
- provider
- resource
- bounded logs
- metrics
- estimated/current usage
- recovery state

を返せるようにする。

---

### `experiment_result`

目的：
完了した実験の結果を取得する。

返却：

- status
- metrics
- result summary
- artifact metadata
- exact source SHA
- exact plan fingerprint
- exact workload image digest
- provider evidence
- GPU actually used
- runtime
- known cost
- cleanup status

`simulation`、CPU、mock-providerの結果をGPU実験成功として表示してはならない。

---

### `experiment_cancel`

目的：
実行中ジョブを停止する。

停止は、新規実行より強い可用性を持たせる。

新規実行スイッチがOFFでも、

- cancel
- cleanup
- recovery
- reconciliation

は既存ジョブについて可能であること。

---

## 3. ChatGPTの会話に適した設計

MCPの戻り値はモデルが解釈しやすい構造化JSONにする。

巨大なstdoutやprovider raw responseをそのまま返さない。

各responseには可能なら：

```text
status
human_summary
machine_state
next_allowed_actions
blocking_reason
```

を含める。

例えばGPUが利用できない場合、

```json
{
  "status": "blocked",
  "human_summary": "無料GPU枠を現在確認できません。",
  "blocking_reason": "FREE_GPU_UNAVAILABLE",
  "next_allowed_actions": [
    "retry_later",
    "run_cpu_smoke_test",
    "prepare_paid_plan"
  ]
}
```

のようにする。

これによりChatGPTが次に何を提案すべきか判断できる。

---

## 4. 無料資源の役割

目標は「無料GPUをかき集めること」ではない。

目標は：

**ChatGPTから実験を頼んだ際、使用可能かつ正規に利用できる中で最小コストの資源を自動選択できること。**

provider候補について、最新の公式API・規約を確認して実装する。

候補：

- local CPU
- local CUDA/ROCm GPU
- GitHub Actions CPU
- Modal
- Kaggle
- Hugging Face / ZeroGPU
- user-operated Colab
- RunPod
- その他正式APIを持つ資源

分類：

```text
LOCAL
FREE
FREE_QUOTA
CREDIT_BACKED
PAID
MANUAL_ONLY
UNSUPPORTED
UNKNOWN
```

無料利用上限やクレジットを回避する実装は禁止。

利用規約に反する自動化も禁止。

---

## 5. Resource selection

デフォルト：

```text
FREE_FIRST
```

選択順序は単純な価格順ではない。

以下を考慮する。

1. workloadを実行可能か
2. 必要GPU/VRAM
3. provider利用可否
4. free quota
5. queue/wait
6. runtime limit
7. result retrieval
8. cleanup/recovery能力
9. known cost
10. reliability

ユーザーが「GPUが必要」と指定した場合、CPUへ黙ってfallbackしない。

CPU smoke testを代案として提案することは許される。

---

## 6. ChatGPT会話フロー

以下の会話を成立させる。

### Case A — 無料GPUあり

User:

> このcommitで学習を100 stepだけ試して。

ChatGPT:

1. capabilities
2. prepare
3. 必要ならapproval
4. submit
5. run_idを報告

後続のユーザー：

> どうなった？

ChatGPT:

6. status

ユーザー：

> 終わった？

ChatGPT:

7. result

---

### Case B — 無料GPUなし

User:

> GPUで試して。

ChatGPT:

```text
現在利用可能な無料GPUは確認できません。
CPU smoke testなら無料で実行可能です。

有償GPU候補：
RunPod ...
推定上限 ...
```

勝手に課金しない。

---

### Case C — provider障害

実行状態をUNKNOWNにしただけで同じジョブを再submitしない。

まずreconcileする。

既存provider resourceを発見した場合は、それを同じrun_idへ再接続する。

---

### Case D — ChatGPTセッションが終了

ChatGPT接続が切れてもジョブは失われてはならない。

後日：

> 昨日の実験どうなった？

という要求からrunを検索・状態確認できる設計にする。

必要なら次のread-onlyツールを追加してよい。

`experiment_list`

ただしowner/subject isolationを保持する。

---

## 7. 非同期性

GPU実験をChatGPTの1回のMCP callで完了まで待たない。

必ず：

```text
prepare
submit
return run_id
```

で切る。

workerが非同期実行する。

ChatGPTは別tool callで状態を確認する。

この設計は、Gateway request timeoutやChatセッション寿命からGPU job lifetimeを切り離すため必須。

---

## 8. 認証

ChatGPT -> MCPアクセスには、既存のOAuth/OIDC境界を利用する。

provider credentialをChatGPTへ渡さない。

構造：

```text
ChatGPT OAuth identity
        ↓
Gateway
        ↓
owner authorization
        ↓
worker-side provider secret
```

RunPod、Modal等のcredentialはworkerだけが保持する。

target repository、provider log、model output等をcontrol-plane instructionとして扱わない。

---

## 9. Provider backend

既存：

```text
DemoBackend
ModalSandboxBackend
ExistingRunPodBridge
```

を壊さずに拡張する。

共通provider contractとして最低：

```text
start
inspect
cancel
reconcile
```

を維持し、必要なら：

```text
capabilities
quota
quote
result
cleanup
```

を追加する。

MCP layerにprovider固有APIを漏らさない。

ChatGPTは：

```text
run this experiment
```

だけを知ればよい。

---

## 10. 実験登録方式

ChatGPTから任意shell commandや任意container imageをproviderへ送れる設計は禁止。

まずoperator-reviewed workload registryを採用する。

例：

```text
orbitune-tokenizer-smoke
orbitune-train-small
cuda-smoke
pytorch-gpu-info
```

各workloadが持つ：

- source repository
- commit
- immutable image or trusted build
- parameters schema
- GPU requirement
- max runtime
- max cost
- result schema

ChatGPTは登録済みparameterだけを変更できる。

将来的なgeneric experiment supportは別のsandbox/security milestoneとする。

---

## 11. 実際に動くことの定義

完成条件はunit test greenではない。

### Test 1

ChatGPTから：

> gpu-controlで現在利用可能な実験環境を調べて。

MCP callが実際に発生し、正しいprovider一覧が返る。

### Test 2

ChatGPTから：

> 無料で実行できるCPU smoke experimentを開始して。

prepare → submit → status → result が成立する。

### Test 3

ChatGPTから：

> 同じ実験をもう一度実行して。

idempotencyが意図通り働き、誤った二重実行が起きない。

### Test 4

実行中にworkerを再起動する。

同じrun_idからrecoverできる。

### Test 5

ChatGPTからcancelする。

実provider資源が解放されたことを確認する。

### Test 6

利用可能な無料GPU providerが正式に設定されている環境では、実GPU smoke testを行う。

出力には必ず：

```text
gpu_used = true
provider
GPU model
run_id
source SHA
exit status
result
cleanup status
known usage/cost
```

を含める。

provider credentialや無料枠が用意されていなければBLOCKEDとし、fake成功を作らない。

---

## 12. ChatGPT側の独立受入試験

最終的に別ChatGPTセッションで、利用者がコードやCLIを操作せず、会話だけで次を実行する。

```text
gpu-controlを使ってください。

まず利用可能な計算資源を確認してください。

追加料金なしでGPUが使えるなら、
登録済みの最小CUDA smoke experimentを実行してください。

無料GPUが利用できない場合は、
有償GPUを勝手に使わず、
ローカルまたは無料CPU smoke experimentを実行してください。

実行したらrun_idを教えてください。
```

その後：

```text
さっきのrun_idの状態を確認してください。
```

さらに：

```text
結果を取得して、
実際に使ったCPU/GPU、
provider、
source SHA、
実行時間、
主要metrics、
cleanup状態、
既知の費用を説明してください。
```

この一連がChatGPTチャットだけで成立することを、製品受入条件とする。

---

## 13. 作業順序

1. 現在のmainと既存Gatewayを再監査
2. 監査PR #43との差分評価
3. Remote MCPを実際のChatGPT tool surfaceとして整理
4. MCP tool schema安定化
5. local/demoではない実CPU backendを通す
6. durable status/result/cancel/recovery完成
7. ChatGPTとのOAuth/MCP接続を実環境で確認
8. 無料providerを1つずつ追加
9. 実GPU smoke test
10. RunPod有償pathを最後に完成
11. 別ChatGPTセッションによる独立受入

一度に全providerを実装しようとしない。

**まずChatGPT → gpu-control → 1つの実計算backend → ChatGPT resultという縦方向の一本を完全に通す。**

これがPASSしてからproviderを増やす。

---

## 14. リリース判定

以下を別々に判定する。

```text
MCP_CONNECTIVITY
CHATGPT_TOOL_USABILITY
CPU_EXECUTION
FREE_GPU_EXECUTION
PAID_GPU_EXECUTION
RECOVERY
CANCELLATION
RESULT_RETRIEVAL
SECURITY
```

各項目：

```text
PASS
FAIL
BLOCKED
UNCERTAIN
```

とする。

mockやsimulationは別カテゴリーとし、実実行PASSには数えない。

---

## 最重要原則

このプロジェクトの成功条件は、

「GPU APIを実装した」

ではない。

**「ChatGPTのチャットで実験を頼んだら、本当に実験が走り、あとから同じチャットまたは別チャットで状態と結果を取得できる」**

ことである。

そのユーザー体験から逆算して設計・実装すること。

作業を開始せよ。

## 2. 〈応用・転用例〉

この設計なら将来、あなたがChatGPTで

> 「この実装変更って本当に速くなった？GPUで小さい比較実験して」

と書くだけで、

**ChatGPT → `experiment_prepare` → `experiment_submit` → worker → GPU → `experiment_result`**

まで流せます。

重要なのは、**ChatGPT自身がGPUを持つのではなく、ChatGPTがあなたの `gpu-control` MCPを操作する**という構成です。

なので優先順位も明確です。

**最優先は無料providerを大量追加することではなく、ChatGPT ↔ MCP ↔ 1つの本物backendを完全に通すことです。**

それができればModalでもKaggleでもRunPodでも、provider registryへ横展開できます。

## 3. 〈次に考える問い〉

最初の縦通し試験は、

**「ChatGPTからCPUの実ジョブを起動して結果を返す」→「次に無料GPU」**

の順にするのが合理的です。

自分で考える問いは、**「別チャットを開いた後でも『昨日の実験結果を見せて』だけで、そのrunを安全に特定できる必要があるか？」**です。ここをYESにすると、MCPのrun検索・identity設計まで最初から正しく作れます。
