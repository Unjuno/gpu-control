# Kaggle training and Hugging Face ZeroGPU chain — 2026-11-22

Status: **PASS for one fixed, owner-bound, free-only end-to-end GPU chain.**

## Kaggle training

- Run: `87d373020c762fa3999435553a12de87`
- Provider: Kaggle, Tesla T4, `gpu_used=true`, `simulation=false`
- Fixed Orbitune source: `44a1b806160ab5bc721a370d034a6dfcb28f27a8`
- Fixed image: `sha256:09742cdf89ec6646e0a227bfd88252aed7b7a44a854899d8bd3eea8da6a9f8bd`
- Workload: 100 training steps; first loss `5.361542224884033`, final
  loss `5.325594425201416`, validation loss `5.315847873687744`
- Checkpoint checksum: `b990b1468bc60d8f461c32742bd171349c1463a5d96d4def14442399187db6e0`
- Checks: exact Kaggle version and separate checkpoint reload
- Cost classification: `FREE_QUOTA`, known cost `$0`
- Terminal state: succeeded; cleanup confirmed

The private output archive was published to
`Unjuno/gpu-control-orbitune-artifacts` at revision
`23591e175a48c75b761b84ba9aefc18c18cacfa4`, path
`runs/87d373020c762fa3999435553a12de87/orbitune-output.zip`, SHA-256
`d5328a0d84e063c5c9512773a60d306acfe5ee39a755a7d05c71bcac46bf28a2`,
size 1,737,429 bytes. The repository is private.

## Hugging Face ZeroGPU evaluation

- Run: `58ca7f863d597fdf8612913757c9117a`
- Provider: private Hugging Face Space
  `Unjuno/gpu-control-orbitune-zero-gpu`
- Space revision: `2e9df7dcd8815cf3059ae94ce6504315e63a85ab`
- Fixed contract digest:
  `sha256:5d0757c0c6d35514bdd26618a11e028b635d766612c18404551007b2c168ac68`
- Device: `NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 2g.48gb`
- `gpu_used=true`, `simulation=false`, exit code 0
- Evaluation score: `5.315847873687744`
- Returned checksum matched the Kaggle checkpoint checksum above
- Checks: approved Space contract and ZeroGPU quota checked
- Cost classification: `FREE_QUOTA`, known cost `$0`; paid fallback forbidden
- Terminal state: succeeded; cleanup confirmed

The first evaluation attempts failed because the Space did not yet have a valid
artifact-read secret. A fine-grained token restricted to read-only access for
the single private artifact repository was registered once as `HF_READ_TOKEN`.
Its validity and artifact access were checked without exposing the value, the
Space restarted on ZeroGPU, and the next fixed evaluation succeeded. This is a
persistent provider credential; it is not issued per experiment.

This record proves the live fixed training-to-private-artifact-to-ZeroGPU route.
It does not remove owner binding, immutable plan review, budget checks, replay
prevention, or cleanup requirements for later runs.
