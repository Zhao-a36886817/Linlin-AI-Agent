# Supply-Chain Security and Release Promotion

Every pull request and main-branch push validates Python, Node and Tauri code on
Windows, Linux and macOS. Workflow permissions default to read-only, checkout does
not persist credentials, third-party Actions are pinned to full commit SHAs, and
untrusted `pull_request_target` execution is prohibited.

The supply-chain job scans tracked text for high-confidence secrets, produces a
deterministic CycloneDX 1.5 SBOM from the pinned Python, npm and Cargo dependency
files, and runs ecosystem dependency audits. CI uploads only the generated SBOM;
hidden files are not included.

Local Gate validation uses P21-dedicated directories under the ignored test cache,
instead of either a shared workspace path or a user-profile pytest root that may be
locked on Windows. The local npm audit cache uses the same ignored cache boundary,
so the audit does not depend on a writable user-profile cache. These local
reliability settings do not change the CI audit or release workflows.

Release candidates are manual-only. The operator must type `PROMOTE`, and the job
uses a protected `production` GitHub Environment so repository administrators can
require reviewers. Tauri signing values exist only as environment secrets and are
never command arguments or output. Each native bundle receives a GitHub/Sigstore
attestation binding it to repository, workflow and commit identity. No workflow
automatically publishes a production release.

## Verification and compromise drill

Before promotion, verify the P20 Ed25519 metadata/package signature, compare the
bundle SHA-256 with provenance, inspect the SBOM, and run `gh attestation verify`
against the repository owner. A compromise drill changes one copied artifact byte
and confirms both local provenance comparison and signature verification reject it.

If a signing key, runner or dependency is suspected compromised: disable the
production Environment, revoke/rotate the signing secret, stop promotion, retain
evidence, mark affected candidate digests denied, rebuild from the last reviewed
commit on clean runners, regenerate SBOM/provenance, and reverify before resuming.
Rollback uses the last independently verified signed installer and never deletes
user data.
