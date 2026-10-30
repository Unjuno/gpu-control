# P3 deployment topology decision

Date: 2026-10-28
Status: **Topology selected; provider, public domain, budget, and deployment remain unapproved and unselected.**

## Decision

Use one dedicated Linux host running the Gateway API, execution worker, and
recovery supervisor as separate systemd services. Keep PostgreSQL managed by
the existing Neon project. Put artifacts on a dedicated, fixed-size filesystem
mounted at `/var/lib/gpu-control/artifacts`. Terminate public TLS at a reverse
proxy and bind the Gateway API to loopback. Only the worker and recovery
supervisor may access the local Docker daemon; the API receives no Docker socket
or provider credentials.

This selects a topology, not a cloud provider, VM size, region, DNS name, price,
purchase, or production deployment. Those remain operator decisions. Local CPU
admission stays disabled until the independent review and P3 acceptance gates
pass. Paid/GPU settings remain parked.

## Evidence and rationale

- The current Vercel production deployment is still the pre-vertical `main`
  revision. The Vercel project has no custom domain, and its environment
  metadata could not be read through the connected account. No deployment
  environment value is inferred from source code.
- The current implementation has a continuously polling execution worker and a
  separate recovery supervisor. The existing Vercel Function is configured
  with a 30-second maximum request duration; it does not host either persistent
  process.
- `ArtifactStore` currently reads and writes a local filesystem path. API,
  worker, and supervisor therefore need a common persistent artifact mount.
  A dedicated host supplies that boundary directly and permits an OS-enforced
  filesystem size limit plus a separate free-space floor.
- The checked-in systemd templates already separate API and worker daemon
  access, run under a dedicated service account, and keep the API on loopback.
  These templates have passed syntax/reference checks in Debian 12/systemd 252,
  but have not started on a selected target host.
- The existing Neon production branch is unversioned Gateway v1 and contains
  local OAuth admin/session state. A local isolated PostgreSQL 16 rehearsal
  migrated a synthetic v1-shaped database to v6 while preserving synthetic run
  and OAuth data. After schema v7 added OAuth grant-family metadata, the exact
  operator `--init-db` entrypoint was rerun twice against an isolated synthetic
  v1 PostgreSQL 16 database and reached v7 idempotently while preserving run
  and OAuth rows; future schema v99 was rejected without mutation. Production
  backup, restore, migration review, and migration remain pending; see
  [`2026-10-28-neon-first-schema-migration.md`](../acceptance/2026-10-28-neon-first-schema-migration.md).

## Alternatives

| Option | Assessment |
| --- | --- |
| Vercel Functions for API and worker | Rejected for the worker: the current app needs persistent worker/supervisor processes and shared filesystem artifacts; a bounded request invocation does not provide those. |
| Vercel Sandbox + Drive | Not selected. Current Vercel docs describe sessions up to 45 minutes on Hobby and 24 hours on Pro/Enterprise, with snapshot-based persistence and Drive for storage outside the sandbox. The docs recommend a traditional VM or Functions for a continuously running server. A reliable resume scheduler, account eligibility, Drive limits/pricing, cross-process locking, and filesystem quota behavior are unverified. See [Sandbox duration and persistence](https://vercel.com/kb/guide/vercel-sandbox-duration-and-persistence) and [Vercel Sandbox](https://vercel.com/sandbox). |
| Dedicated Linux host + managed Neon | Selected topology. It matches the current systemd units, process model, shared filesystem artifact store, and database boundary with the fewest runtime changes. The specific host, region, cost ceiling, public TLS name, backup policy, and alert sink are not selected. |

## Provider and size shortlist (read-only research, 2026-10-28)

The first provider to validate is **Amazon Lightsail Linux/Unix VM**, because it
offers both Tokyo (`ap-northeast-1`) and Singapore (`ap-southeast-1`), fixed
monthly bundles, and attachable block storage. This is a candidate, not a
provider decision or provisioning approval. A read-only check of the current
official price tables on 2026-10-28 lists the public-IPv4 2 GB bundle at 2 vCPU,
60 GB system SSD, 3 TB transfer, and $12/month; the 4 GB bundle is 2 vCPU, 80 GB
system SSD, 4 TB transfer, and $24/month. Additional block storage is $0.10 per
allocated GB-month, with an 8 GB minimum. A separate 32 GB artifact disk
therefore adds $3.20 per month: estimated compute-plus-disk baseline is $15.20
for 2 GB or $27.20 for 4 GB, before snapshots, transfer overage, tax,
DNS/domain, backups, and provider/account-specific charges. Lightsail snapshots
are listed at $0.05 per GB-month. These bundles include substantial system
storage and transfer allowance, but that does not replace the separate fixed
size artifact filesystem or prove actual project traffic fits the allowance.
[Lightsail Linux bundle sizes and prices](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html),
[block storage pricing](https://aws.amazon.com/lightsail/pricing/),
[snapshot pricing](https://aws.amazon.com/lightsail/pricing/).

The existing Neon database is in Singapore. **Singapore is the first region to
measure** because it matches that database region; whether this produces lower
round-trip latency or avoids transfer charges is unverified, since Neon and
Lightsail are separate services/accounts and the planned connection is not a
private VPC link. Tokyo is the alternative if measured API/user latency or
operational requirements favor Japan. Lightsail documents both regions and
lists excess outbound transfer at $0.12/GB for Singapore and $0.14/GB for
Tokyo. These are instance-plan excess outbound transfer rates, not object
storage or distribution rates; the official instance FAQ was rechecked on
2026-10-28 and confirms both figures. [Lightsail Regions](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html),
[instance regional transfer overage](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-data-transfer-allowance.html).

DigitalOcean is now priced on the same separate-volume basis. Its Basic
2 GiB / 1 vCPU / 50 GiB Droplet is $12/month with 2,000 GiB included transfer;
the 4 GiB / 2 vCPU / 80 GiB plan is $24/month with 4,000 GiB. A 32 GiB
DigitalOcean Volume is $3.20/month, giving compute-plus-artifact-volume
baselines of $15.20 and $27.20/month. Singapore is available; the current
regional list does not offer Japan. Bundled Droplets have a monthly price cap,
and additional public-network transfer is $0.01/GiB after the team's pooled
allowance. Backup/snapshot retention, DNS/domain, tax, and account-specific
charges remain outside those totals. This comparison is still not an approved
provider or budget decision. [Droplet pricing and plans](https://www.digitalocean.com/pricing/droplets),
[Volume pricing](https://docs.digitalocean.com/products/volumes/details/pricing/),
[bandwidth billing](https://docs.digitalocean.com/platform/billing/bandwidth/),
[Droplet regional availability](https://docs.digitalocean.com/products/droplets/details/availability/).

For a first isolated rehearsal, 2 GB is the lower-cost candidate; for a
long-running API + worker + supervisor and container workload, 4 GB is the
safer sizing candidate until a target-like memory test establishes otherwise.
That sizing recommendation is an inference from the process topology, not a
measured minimum. Validate actual workload peak memory, Docker disk use, and
artifact growth before freezing a size. The account owner has not set a monthly
cost ceiling; the cost question remains open, and no VM, disk, snapshot, DNS,
or other paid resource has been created.

## Public origin and OAuth constraint

The deployed ChatGPT-facing origin currently uses `gpu-control.vercel.app`;
read-only Vercel project metadata showed no custom domain. A Linux host therefore
needs an operator-selected public HTTPS origin or a reviewed proxy arrangement.
Changing the built-in OAuth issuer changes the owner hash used for runs and
artifact scopes. Do not change the public origin or migrate existing Neon owner
state as part of host provisioning by default. First choose how to preserve or
replace the origin, take and verify a paired backup, and review whether the
offline owner migration is actually required. Never reveal or copy OAuth
credentials into this decision record.

## Required before implementation on a real host

1. Select the host/provider, region, monthly cost ceiling, and domain. Verify
   current pricing, support, access controls, and account-level limits.
2. Verify SSH/admin ownership, TLS proxy, firewall, service account, Docker
   trust boundary, persistent filesystem quota, and alert destination.
3. Rehearse the paired Neon/artifact backup and restore with a second operator;
   the local synthetic PostgreSQL 16 v7 drill has passed, including artifact
   bytes and OAuth grant/revocation state, but it does not substitute for this
   second-operator rehearsal. Review the current v1-to-v7 schema migration and
   OAuth preservation before applying it to production.
4. Deploy the same reviewed source revision, check `/readyz`, complete actual
   ChatGPT OAuth/tool scan, and run/retrieve a registered local CPU smoke from
   two conversations.
5. Complete the seven-day CPU observation, timed RPO/RTO drill, cancellation,
   cleanup, quota-failure, and alert-delivery acceptance before enabling local
   CPU policy.

These requirements are gates, not authorization to purchase, deploy, change DNS,
mutate Neon, enable CPU admission, or perform paid/GPU execution.

## Current pricing recheck (2026-10-28)

Rechecked the official AWS tables: the public-IPv4 Linux bundle remains $12/mo
for 2 GB RAM, 2 vCPU, 60 GB SSD and 3 TB transfer, and $24/mo for 4 GB RAM,
2 vCPU, 80 GB SSD and 4 TB transfer. Lightsail block storage remains
$0.10/allocated-GB-month (32 GB = $3.20/mo), and snapshots $0.05/GB-month.
The arithmetic baselines remain $15.20/mo and $27.20/mo before snapshots,
transfer overage, tax, domain, DNS, and off-host backup. Instance-plan outbound
overage remains $0.12/GB in Singapore and $0.14/GB in Tokyo. Sources:
[bundle prices](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html),
[block storage and snapshot pricing](https://aws.amazon.com/lightsail/pricing/),
[regional transfer overage](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-data-transfer-allowance.html).
This confirms the shortlist inputs only; it does not select a host or establish
the operator's acceptable monthly cap. No resource was created.

## DigitalOcean comparison refresh (2026-10-28)

The live official price page and current product documentation now confirm the
full VM-plus-32-GiB-volume arithmetic for both shortlisted sizes: $15.20/month
for 2 GiB and $27.20/month for 4 GiB. DigitalOcean's Basic bundles include a
monthly compute cap and 2/4 TiB transfer respectively, but overage is
$0.01/GiB and the allowance pools at the team level. Volume charges accrue
while detached too. DigitalOcean lists Singapore and no Japan datacenter, so
the 2-GiB plan has one shared vCPU versus Lightsail's two vCPUs at the same
baseline price; the 4-GiB plans both list two vCPUs. These are arithmetic
comparisons from public list prices, not account-specific checkout quotes.
Backups, snapshots, domain/DNS, taxes, payment terms, latency to Neon, storage
quota behavior, service support, and user-set budget remain unresolved. No
provider was selected or provisioned. Sources: [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets),
[DigitalOcean Volume pricing](https://docs.digitalocean.com/products/volumes/details/pricing/),
[DigitalOcean bandwidth billing](https://docs.digitalocean.com/platform/billing/bandwidth/),
[AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/).
