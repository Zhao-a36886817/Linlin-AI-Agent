# P18 Resource Governance Baseline

The approved P18 baseline measures admission behavior, not machine-specific wall
clock speed. `ResourceGovernor.snapshot()` records active/waiting operations,
reserved CPU units and bytes, peak values, completions, overload rejections,
timeouts, and cancellations.

The regression suite drives six concurrent operations through a two-slot governor,
verifies provider-specific serialization, validates immediate rejection when the
bounded queue is full, and performs an 80-operation short soak. Every timeout and
cancellation must return active CPU and memory reservations to zero. These
deterministic invariants are the cross-platform performance baseline; absolute
latency benchmarks may be recorded separately for a specific release machine but
must not weaken security or correctness checks.
