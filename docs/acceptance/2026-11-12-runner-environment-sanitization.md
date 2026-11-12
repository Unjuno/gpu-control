# Runner environment sanitization — 2026-11-12

## Finding

The live LaunchAgent's launchd record exposed the inherited `SSH_AUTH_SOCK`
setting. The fixed workload container already receives a bounded environment,
but the host Runner needed an explicit environment boundary before it loads its
Keychain credentials.

`ps eww` continued to display the launch-time environment for a controlled
Python process after `os.environ.clear()`. A separate check in that same
process called the native C `getenv("SSH_AUTH_SOCK")` after clearing and
returned false. Therefore `ps eww` is not used as proof of the current C
environment in this macOS setup; it may show the original exec-time block.
No socket value was recorded.

## Deployed mitigation

- The correct baseline was opened through the Sites source helper at the exact
  production Version 15 source commit
  `e3cfaf71c5f084c6a6ab40adbae8e189327197ad`. The earlier local Site checkout
  was stale and had unrelated uncommitted files; it was not pushed.
- `runner/macos_keychain_launcher.py` now clears inherited environment state
  before loading credentials and retains only the fixed Site/workload
  configuration, `PATH`, `HOME`, and `LANG`. This removes inherited SSH-agent,
  proxy, Docker endpoint, Python path, and environment credential settings.
  Bearer credentials continue to come from Keychain and remain only in memory.
- `runner/macos_launch_agent.py` explicitly pins `HOME` and `LANG` in its
  secret-free plist. The sanitized launcher and updated plist were installed
  while free CPU admission was disabled and all 28 listed runs were terminal.
- The new source commit is `82d9a5dba4af54a60dc5e48cbbe6f16a1ebfa4e3`.
  Private Site Version 16 deployment `appgdep_6af546ffca2081918414b1bc0725782f`
  succeeded with MCP ready. The runtime environment was applied as revision 13
  with CPU admission closed, then revision 14 reopened free CPU admission.
- The LaunchAgent stop/install/start sequence succeeded. The installed
  `run.py` and Keychain launcher are byte-identical to Version 16 source; the
  plist and both installed Python files are mode `0600`; `plutil -lint` passes.
  Sites accepted a fresh heartbeat for the registered source and image after
  restart (`runner_ready=true`) before admission was reopened.
- A post-cutover ChatGPT-originated run
  `eacc26ff2ad54cf69a1ee7665325b197` succeeded under a `$0.00` cap. It generated
  four tokens in 142 ms, passed all nine workload checks, reported
  `gpu_used=false`, and confirmed container cleanup. The separate result and
  artifact calls succeeded. The complete 962-byte R2 artifact SHA-256
  `39ff3134a0b69d34ea8e4d220a4445583c803eb6382c88593a291486cffb5030` matched
  an independent hash of the returned bytes.
- Local verification on the exact Version 15 baseline plus this patch: 24
  Runner tests, 24 Worker/D1 tests, `npm run build`, and `npm run validate`
  passed. Paid execution remained parked throughout.

## Remaining security and operations gates

- [ ] Rotate the Runner bearer credential and separately verify the Keychain
  ACL; this rollout reused the existing Keychain items without reading or
  changing their values.
- [ ] Add an explicit in-process environment audit signal if future macOS
  tooling can validate it without relying on `ps eww`'s launch-time snapshot.
- [ ] Repeat the post-result/R2 crash-window and process-loss acceptance.
- [ ] Complete isolated D1/R2 restore, artifact orphan cleanup, and
  separate-account owner isolation/revocation.
- [ ] Retire external Vercel and Neon resources after owner action and Neon data
  disposition. Paid and GPU admission remain parked.
