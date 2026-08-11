# Enterprise Policy Enforcement

P19 policy is deny-by-default. A privileged caller constructs a typed request from
an already authenticated identity, checks that identity, resource and workspace
tenant identifiers align, and calls `PolicyRuntime.require()` before invoking the
existing Provider, Tool, Workspace, or Credential Runtime. Policy does not replace
authentication or those execution boundaries.

Rules match exact roles and actions. Explicit deny wins over allow independently of
configuration order; no role, including an owner-like subject name, receives
implicit administrative access. Every decision may be sent to an injected local
audit sink and contains correlation, subject, tenant, action, reason, and matched
rule identifiers only. Identity/request models reject unknown fields so credentials
cannot be attached to policy records.
