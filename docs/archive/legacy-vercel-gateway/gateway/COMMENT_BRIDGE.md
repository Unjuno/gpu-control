# GitHubコメントから実験を操作する

## 構成と現在の範囲

```
ChatGPTのGitHub接続 / 人間のGitHubコメント
  -> 専用Issue #48
  -> gateway-comments.yml (main上の固定workflow)
     -> /gpu local: CPUの小さい学習をDockerで実行
     -> その他: GitHub OIDC -> /api/ci/comment
                              -> 既存ExperimentService
                              -> Neonの実験キュー
                              -> 独立worker -> Modal / 既存RunPod bridge
```

Remote MCP `/mcp` とWebMCPはそのまま残る。コメント経路はMCPを経由せず、同じ実験サービスへ入る。GitHub Actions runner上で長時間GPUジョブを待たない。

**コメント経路はGPU課金承認ではない。** `prepare`は計画作成のみ。`submit`もWebでその計画が承認されていない場合は拒否する。`queued`は「GPU実験に成功した」ではない。独立worker、登録済みworkload、現在の見積り、各provider固有の実行条件が必要。

既存RunPod core、既存RunPod CI、repository-stateのparked設定、実行フラグ、provider資格情報は変更しない。独立した既存RunPod CIの結果が自動でNeonへ入るわけでもない。共有結果を見るには既存の `GATEWAY_RUNPOD_FACTORY` アダプターでその経路を明示的に接続する。

## 最初の操作

対応PRをmainにマージし、同じコミットがVercelへデプロイされた後、`Unjuno/gpu-control` の **Issue #48** にowner本人の新規コメントで送る。

```text
/gpu local
```

これはrepository所有の `workloads/tiny-lm/tiny_lm.py` のみを実行する。コメントから任意のshell、repository、Dockerfile、URL、imageを指定する機能はない。結果はIssue返信、Actions Summary、7日保持の小さいJSON artifactに出る。

```text
/gpu integrations
```

これは登録されたprovider/workloadを確認する。`enabled: false` のproviderは有効化されていない。

```text
/gpu prepare
{"workload":"demo","runtime_seconds":60,"max_cost_usd":"0.10"}
```

返された `run_id` と `fingerprint` を確認し、Web画面で同じ実験の計画を承認する。金額文字列は**上限**であり課金見積りでも固定価格でもない。デモはGPUなしだが、同じ承認経路を検証する。

```text
/gpu submit
{"run_id":"ここを返された32桁のrun_idに置換"}
```

上の説明用run_idは有効な入力ではない。実際の値へ置き換える。

```text
/gpu list
```

```text
/gpu status
{"run_id":"ここを返された32桁のrun_idに置換"}
```

```text
/gpu cancel
{"run_id":"ここを返された32桁のrun_idに置換"}
```

`cancel_requested`は取消受付であり、外部providerでの停止完了と区別する。停止確定はworkerの観測結果で確認する。

## 追加のGitHub Secretsは不要

Actionsの `id-token: write` で発行される短命JWTを、固定URLへ送る。Neonの接続文字列、所有者パスワード、Modal/RunPodキーはGitHubへコピーしない。

サーバー側の `gpu_gateway/ci_policy.json` は、trusted sourceとして次を明示する。

- repository名と数値ID、owner/actorの数値ID
- 専用Issue番号、main、固定workflowのパス
- gatewayのHTTPS origin

JWTの署名、issuer、audience、subject、repository/owner/actor、event、workflow、SHA、期限を検証する。トークンは一般のMCP APIや承認APIには使えない。旧形式とimmutable ID入りのGitHub subject両方に対応するが、数値IDの検証は必須。

`workflow_sha` と `sha` はVercelの `VERCEL_GIT_COMMIT_SHA` と一致する必要がある。新しいmainのデプロイが未完了ならfail closed。デプロイ完了後に新規コメントを送る。Actionsの再実行 (`run_attempt > 1`)、PR上のコメント、編集コメント、30分を超えた古いコメントは受け付けない。

サーバーはGitHub APIからコメントとIssueを再取得し、actor、Issue、本文hash、作成/更新時刻も検証する。GitHub APIの一時障害・rate limit時に推測で進めない。

初期owner対応付けは既存の**単一ownerのlocal OAuth**に限定。外部OIDCへ変更した際は自動で同一ユーザーと推定せず、ブリッジを拒否する。別repositoryへのforkはpolicyとworkflow guardを自分の値へ変え、レビューする。停止はpolicyの `enabled` をfalseにする。

## ローカルで小さく試す

依存なしのCPU版:

```sh
python gateway/workloads/tiny-lm/tiny_lm.py
```

Docker版（repository rootから）:

```sh
docker build -t gpu-control-tiny gateway/workloads/tiny-lm
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 10001:10001 \
  --pids-limit 32 --memory 128m --cpus 1 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m gpu-control-tiny
```

CIではさらに30秒のtimeoutと終了時のcleanupを行う。CPU base imageはタグなので、厳密なimage再現性を主張しない。実際に解決されたimage IDを結果へ記録する。再現性が必要な運用では確認済みdigestへ固定する。

サンプルは固定された公開文字列、95個の隣接文字ペア、169パラメーター、40更新のbigram LM。損失が有限で初期値より改善したら成功。学習済み言語モデルの品質評価やGPU性能ベンチマークではない。

同じ演算をPyTorchで比較する場合は、PyTorch導入済み環境で:

```sh
python gateway/workloads/tiny-lm/tiny_lm.py --backend torch --device cpu
```

## GPUへ渡す

同じ `tiny_lm.py` は `--backend torch --device cuda` に対応する。CUDAを指定してCUDAがなければ失敗し、CPUへ黙って切り替えない。`GPU_CONTROL_CONFIG_JSON` は `steps` (1〜200) だけを受け取る。device/backendはoperatorが固定するargv側で決める。

`Dockerfile.gpu` はoperatorが確認した **PyTorch/CUDA対応base imageのdigest** を `BASE_IMAGE` として渡すテンプレート。CUDAイメージのダウンロードやModal imageのビルド/登録を、このコメントworkflowが勝手に行うことはない。

Modalでは既存の `ModalSandboxBackend` とworkerを使い、次を満たしたworkloadを登録する。

- 実際にビルド済みの `im-...`、immutable source revision
- 固定argv: `python -I /work/tiny_lm.py --backend torch --device cuda`
- GPU、CPU、RAM、runtimeの上限
- 現在のall-in見積りと有効期限（サンプル価格は使わない）
- parameters schema: `steps`だけ、integer 1〜200、additionalProperties false

コメントからはprovider名を直接指定せず、例えば `tiny-lm-t4` という**登録済みworkload ID**を指定する。RunPodおよび将来追加する無料枠providerも、同じregistry/Backend契約の下に置く。新しいproviderに応じた秘密情報・停止/照合処理はworker側へ閉じる。

**実GPUのスイッチ、資格情報、workload登録、独立workerの配置はこのPRで有効化しない。** 初回実GPU検証は費用・停止条件を確定した別の承認済み実験で行う。

## データ露出と障害時

このrepositoryはpublic。Issue/Actions artifactにはrun ID、状態、fingerprint、限定された数値指標のみを返す。生ログ、parameters、manifest、任意のエラー本文、接続情報は返さない。詳細結果はログイン済みWeb画面で確認する。長い学習checkpointはこのブリッジのartifact対象外。

- `invalid_actions_identity`: mainとデプロイSHA、workflow、actor、トークンaudienceを確認。
- `comment_changed_stale_or_unauthorized`: 新規コメントを使用。編集したコメントは使わない。
- `approval_required`: 同じfingerprintの計画をWebで承認する。
- `provider_disabled` / `quote_required`: provider設定と現在の見積りが未完了。
- `worker_recently_seen: false`: queue受付だけ。独立workerを確認する。
- 通信の応答が失われても自動再送しない。`list/status`でまず既存runを確認する。

## 一次資料

- GitHub issue_comment: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issue_comment
- GitHub OIDC claims: https://docs.github.com/en/actions/reference/security/oidc
- Script injection境界: https://docs.github.com/en/actions/concepts/security/script-injections
