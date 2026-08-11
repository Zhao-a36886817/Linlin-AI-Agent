# Linlin Agent LAES Roadmap — P10–P24

**Status:** Proposed planning package  
**Authority:** Future implementation still requires an active LAES phase, ChatGPT Gate Review, and explicit project-owner approval.

This roadmap decomposes the P9 readiness findings into small, sequential gates. Merely listing a phase does not authorize implementation. `.laes/CURRENT_PHASE.yaml` remains the only active-phase authority.

| Phase | Title | Primary exit evidence |
|---|---|---|
| P10 | Memory Runtime Implementation | Memory remains disabled until explicitly enabled |
| P11 | RAG Runtime Implementation | Traversal-safe ingestion and deterministic retrieval pass |
| P12 | MCP Integration | No server is enabled by default |
| P13 | Plugin Runtime and SDK | Invalid or excessive manifests are rejected |
| P14 | Scheduler and Automation Runtime | Jobs can be listed, cancelled and audited |
| P15 | Multi-Agent Orchestration | Delegation depth and concurrency are bounded |
| P16 | Multimodal I/O and Artifact Pipeline | Size, type and path checks reject unsafe input |
| P17 | Observability, Audit, and Diagnostics | Known secrets never appear in output |
| P18 | Performance, Concurrency, and Resource Governance | Budgets and limits are measurable |
| P19 | Enterprise Security and Policy Enforcement | Policy decisions are deterministic and auditable |
| P20 | Desktop Packaging, Installer, and Auto-Update | Supported package checks are reproducible |
| P21 | CI/CD, Signing, and Supply-Chain Security | Windows, Linux and macOS validation is represented |
| P22 | Public and Plugin API Stability | Published contracts have automated tests |
| P23 | Backup, Migration, Data Portability, and Recovery | Round-trip export and restore are deterministic |
| P24 | Enterprise Readiness and v1.0 RC Gate | All required phase gates and evidence are present |

## Dependency chain

`P9 APPROVED → P10 → P11 → P12 → P13 → P14 → P15 → P16 → P17 → P18 → P19 → P20 → P21 → P22 → P23 → P24`

Every arrow means: implementation completion, full validation, completion report, STOP, ChatGPT PASS, and explicit owner approval. There is no automatic continuation.

## Program rules

- P10–P16 introduce bounded capabilities behind disabled-by-default or explicit enablement controls.
- P17–P19 harden operations, resources, and enterprise policy before packaging.
- P20–P23 establish packaging, supply-chain, compatibility, and recovery evidence.
- P24 is a release gate only; it cannot implement missing features or create P25.
- Critical or high security findings block promotion unless resolved through accepted governance.
- All phases preserve Provider, Tool, Workspace, Credential, Agent, and client boundaries.
- Local-first, privacy, test integrity, and Windows/Linux/macOS support remain mandatory.

## Activation procedure

## Owner-approved P25 priority amendment

On 2026-08-09, the project owner explicitly approved creation and priority execution of **P25 — Commercial Runtime Control Center**. P25 integrates the already completed advanced runtimes into one production UI without changing their architecture or bypassing security controls.

The amended execution order is:

`P20 approved -> P25 -> resume P21 -> P22 -> P23 -> P24`

P21 remains incomplete while P25 is active. Its work and failed review evidence are preserved. P24 remains the final release gate and still cannot implement missing features.

After P9 approval, the owner may separately authorize updating the P9 phase roadmap/template so the Supervisor can transition to P10. This planning package does not alter the current phase or existing approval record.
