# Lunaへの実装引き継ぎ

以下をLunaへ渡す。これは実装開始用の指示書であり、計画作成者はまだLunaを起動していない。

---

対象はGitHub `Unjuno/gpu-control`。目的はChatGPTの会話から登録済み実験をprepare/submit/status/result/cancel/listでき、実計算の証拠を会話へ返せる製品を完成させることです。

まず次を順番に読んでください。

1. `docs/specs/chatgpt-native-experiment-control-plane.md`
2. `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md`
3. `docs/superpowers/plans/2026-10-28-gpu-control-first-vertical.md`

これらが本体にない場合、計画の原本は `/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/docs/` にあります。この親フォルダは計画作成時点ではGit checkoutではありません。既存checkoutを使う場合はremoteと変更状態を確認し、なければ `Unjuno/gpu-control` を取得して計画を取り込んでください。無関係な変更は保持してください。

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

最初の報告ではP0の基準確認とPR #43差分表を提示し、そのままT1に進んでください。後続の新規設計が必要な段階は、その段階の受入条件と細分化計画を更新してから実装します。

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
