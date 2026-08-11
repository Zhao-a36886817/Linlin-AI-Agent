# Local Diagnostics and Audit Behavior

Linlin Agent diagnostics are local and in-memory by default. The runtime has no
telemetry transport and never uploads a diagnostic bundle. Callers must provide a
correlation ID and static operational summary; raw prompts, file content, model
output, credentials, authorization values, cookies, and tokens must be placed only
in typed runtime data, not diagnostic summaries.

All event fields pass through redaction. Sensitive attribute keys are replaced in
full, configured secret values and common credential patterns are removed, and
failure events retain only a redacted exception summary and exception type.

Retention is a fixed-size queue configured by `diagnostics_retention`; the oldest
event is discarded when the bound is reached. Health counters remain cumulative
for the lifetime of the process. `bundle()` returns a JSON-compatible local object
containing the retained redacted events and health snapshot. Writing or sending
that object requires a separate, explicit caller action and policy decision.
