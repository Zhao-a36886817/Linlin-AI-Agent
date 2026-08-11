# Advanced runtime readiness audit

P9 is an audit boundary. No advanced subsystem is enabled or registered by
default, and none is ready for production activation.

| Subsystem | Current state | Architecture fit and security risk | Decision | Dedicated follow-up |
|---|---|---|---|---|
| Memory | Empty `backend/app/memory` directory; no imports, API, or tests | Must enter through Agent Runtime. Risks include unintended retention, cross-session disclosure, and deletion-policy gaps. | Keep disabled; design first | Memory phase: approve retention/consent ADR; implement scoped store, deletion, isolation, and tests |
| RAG | No source module or dependency | Must separate Loader, Chunk, Embedding, Retriever, and Citation and use Workspace/Credential boundaries. Risks include poisoned documents, cloud upload, and missing citations. | Not implemented | RAG phase: approve ingestion/trust ADR; offline characterization, traversal-safe loaders, citation acceptance tests |
| MCP | No source module, registration, or network permission | Must be a capability provider behind explicit permissions and Tool Runtime. Risks include remote execution, schema spoofing, and credential/network leakage. | Not implemented | MCP phase: approve protocol/permission ADR; deny-by-default discovery, allowlist, timeout, audit tests |
| Plugins | No plugin loader or manifest contract | Must declare capabilities and pass Tool/Workspace/Credential gates. Risks include arbitrary code loading and supply-chain compromise. | Not implemented | Plugin phase: approve packaging/trust ADR; signed/allowlisted manifests, isolation, lifecycle tests |
| Scheduler | No scheduler module, persistence, or routes | Must trigger approved application actions, never bypass runtimes. Risks include unattended destructive actions and secret-bearing jobs. | Not implemented | Scheduler phase: approve action/consent ADR; disabled defaults, scoped actions, cancellation and audit tests |
| Multi-agent | Only the single ToolLoop orchestration exists | Future coordination must preserve provider/tool/workspace limits. Risks include privilege amplification, loops, and unbounded cost. | Defer | Multi-agent phase after the above: approve delegation/budget ADR; bounded roles, cancellation and authorization tests |

## Required governance before activation

Separate accepted ADRs/RFCs are required for data retention and consent,
document ingestion and citation trust, remote capability permissions, plugin
packaging/supply-chain trust, scheduler authorization/audit, and multi-agent
delegation/budgets. Each follow-up must receive its own LAES phase specification,
tests, Gate Review, and owner approval. Recommended order is Memory, RAG,
MCP, Plugins, Scheduler, then Multi-agent; no P10 is created by this audit.
