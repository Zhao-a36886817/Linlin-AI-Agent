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

Release-candidate evidence is manual-only. The operator must type
`GENERATE_EVIDENCE`, and the job uses a protected `production` GitHub Environment
so repository administrators can require reviewers. This confirmation only permits
evidence generation: it is not P24 approval and it never publishes a release.
Tauri signing values exist only as environment secrets and are never command
arguments or output.

Each runner first creates a deterministic SHA-256 manifest for every file in its
native bundle. Before hashing, a fail-closed staging step copies only the final
installer formats and SBOM into a clean candidate tree. It ignores Tauri build
intermediates and never follows symbolic links, so an AppDir link cannot escape the
bundle or acquire different meaning during artifact upload. The workflow signs the
resulting manifest through the free Sigstore public
good service, using GitHub Actions OIDC, then immediately verifies the exact
workflow certificate identity, GitHub OIDC issuer and Rekor transparency entry.
The Sigstore Action is pinned to a full commit SHA. This route supports private
personal repositories without granting `attestations: write` or making the source
repository public. Rekor is intentionally a public, append-only transparency log;
it records the signing identity and cryptographic material, not the private source
tree or native installer contents.

Windows RC evidence uses the NSIS installer target because MSI/WiX rejects semantic
versions with a textual pre-release identifier such as `1.0.0-rc.1`. Linux produces
DEB and AppImage bundles; macOS produces app and DMG bundles. Selecting NSIS avoids
rewriting the reviewed version merely to satisfy MSI packaging rules.

## Verification and compromise drill

Before any later promotion, verify the P20 Ed25519 metadata/package signature,
compare every bundle SHA-256 with the signed subject and aggregate provenance,
inspect the SBOM, and verify each `.sigstore.json` bundle against the certificate
identity `https://github.com/<owner>/<repository>/.github/workflows/release.yml@refs/heads/main`
and issuer `https://token.actions.githubusercontent.com`. A compromise drill changes
one copied artifact byte and confirms both local provenance comparison and Sigstore
identity verification reject it.

If a signing key, runner or dependency is suspected compromised: disable the
production Environment, revoke/rotate the signing secret, stop promotion, retain
evidence, mark affected candidate digests denied, rebuild from the last reviewed
commit on clean runners, regenerate SBOM/provenance, and reverify before resuming.
Rollback uses the last independently verified signed installer and never deletes
user data.
