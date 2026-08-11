# Linlin Agent — P-Stage Index

This index is informational. AI implementation agents MUST obey `.laes/CURRENT_PHASE.yaml` and MUST NOT implement future phases simply because they are listed here.

| Phase | Title | Primary Goal |
|---|---|---|
| P0 | Build and Test Stabilization | Restore clean compile/lint/test/build baseline |
| P1 | Provider Architecture Stabilization | One canonical Registry → Factory → Manager → BaseProvider path |
| P2 | Ollama and Tool Calling Reference Stabilization | Reliable local reference provider and tool round trip |
| P3 | Tool Registry and Context Efficiency | Small request-scoped tool schemas and lazy/specialized exposure |
| P4 | Workspace, Archive, Git, and Terminal Security Boundary | Prevent workspace/shell/archive escape |
| P5 | Credential and Secret Storage Security | Secure credential abstraction and redaction |
| P6 | Provider Cost and Availability Classification | LOCAL_FREE / FREE_TIER / PAID / UNKNOWN policy |
| P7 | Cross-Platform Dependency and Configuration Normalization | Reproducible Windows/Linux/macOS baseline |
| P8 | Frontend and Tauri Desktop Architecture Convergence | One shared React UI with Tauri shell |
| P9 | Advanced Runtime Readiness | Audit/decompose Memory, RAG, MCP, Plugins, Scheduler |
| P10 | Memory Runtime Implementation | Consent-aware scoped memory through Agent Runtime |
| P11 | RAG Runtime Implementation | Workspace-safe retrieval with citation provenance |
| P12 | MCP Integration | Deny-by-default remote capabilities through Tool Runtime |
| P13 | Plugin Runtime and SDK | Versioned manifests, lifecycle, and capability isolation |
| P14 | Scheduler and Automation Runtime | Consented, auditable approved actions |
| P15 | Multi-Agent Orchestration | Bounded delegation, budgets, and privilege containment |
| P16 | Multimodal I/O and Artifact Pipeline | Safe artifact lifecycle and provider-neutral contracts |
| P17 | Observability, Audit, and Diagnostics | Redacted structured diagnostics and audit evidence |
| P18 | Performance, Concurrency, and Resource Governance | Measured backpressure and resource limits |
| P19 | Enterprise Security and Policy Enforcement | Deny-by-default authorization and tenant isolation |
| P20 | Desktop Packaging, Installer, and Auto-Update | Reproducible signed desktop delivery |
| P21 | CI/CD, Signing, and Supply-Chain Security | Provenance, SBOM, protected signing, and release gates |
| P22 | Public and Plugin API Stability | Versioned contracts and compatibility governance |
| P23 | Backup, Migration, Data Portability, and Recovery | Secure round-trip recovery and rollback |
| P24 | Enterprise Readiness and v1.0 RC Gate | Evidence-based release-candidate go/no-go |
| P25 | Commercial Runtime Control Center | One safe UI for Memory, RAG, MCP, multi-agent, and scheduling |

## Phase Gate Rule

Every phase ends with:

`Implementation → Validation → Completion Report → STOP → ChatGPT Review → Owner Approval`

Only after PASS + owner approval may `.laes/CURRENT_PHASE.yaml` be advanced.
