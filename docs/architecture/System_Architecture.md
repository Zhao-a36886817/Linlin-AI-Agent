# Linlin Agent System Architecture

**Status:** Accepted Baseline  
**LAES Version:** 1.1

## 1. System Intent

Linlin Agent is a cross-platform, local-first, multi-provider AI Agent platform designed for Windows, Linux, and macOS.

It is not merely a provider chat wrapper. The architecture separates UI, agent orchestration, model providers, tool execution, workspace access, memory/RAG, and platform-specific services.

## 2. High-Level Flow

```text
Frontend / Desktop UI
        |
        v
API Layer
        |
        v
Agent Runtime
        |
        +-------------------+
        |                   |
        v                   v
Provider Runtime       Memory / RAG Runtime
        |
        v
Tool Parser
        |
        v
Tool Registry / Tool Runtime
        |
        +-------------------+
        |                   |
        v                   v
Workspace Runtime      Approved Services
        |
        v
Filesystem / Git / Shell adapters
```

## 3. Frontend / Desktop

Responsibilities:

- user interaction;
- chat/workspace/history/provider/model/settings views;
- progress/status display;
- sending typed API requests.

MUST NOT:

- contain provider secrets;
- execute backend tools directly;
- perform agent runtime orchestration.

## 4. API Layer

Responsibilities:

- request/response validation;
- authentication/authorization when applicable;
- streaming transport;
- routing to runtime services.

MUST NOT contain provider-specific business logic that belongs in Provider Runtime.

## 5. Agent Runtime

Responsibilities:

- conversation/session orchestration;
- deciding when provider calls and tool loops occur;
- composing memory/RAG context when enabled;
- maintaining deterministic runtime boundaries.

## 6. Provider Runtime

Responsibilities:

- provider abstraction;
- model discovery/health;
- chat/stream normalization;
- capability metadata;
- provider-specific protocol adaptation.

MUST NOT execute tools directly.

## 7. Tool Runtime

Canonical flow:

`LLM -> Tool Parser -> Tool Registry -> Tool Runtime -> Tool Result -> LLM`

Responsibilities:

- validate tool call shape;
- authorize registered tool;
- validate arguments;
- invoke tool;
- normalize results/errors.

## 8. Workspace Runtime

Workspace Runtime is the security boundary for agent-visible file access.

Responsibilities:

- resolve workspace-relative paths;
- prevent traversal/escape;
- provide safe file/archive operations;
- constrain file-related tools.

## 9. Memory / RAG

Memory and RAG are runtime services, not provider-specific features.

Provider adapters MUST NOT independently own the application's memory architecture or directly parse arbitrary user documents as an architectural shortcut.

## 10. Platform Services

OS-specific features such as keyrings, filesystem peculiarities, process launching, and desktop integration MUST be isolated behind platform-aware services.

## 11. Architecture Change Rule

This document is an accepted baseline. Material changes require the LAES RFC/ADR process and project-owner approval.
