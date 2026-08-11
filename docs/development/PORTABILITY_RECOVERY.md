# Linlin Agent Workspace Portability and Recovery

## Scope

P23 publishes backup format version `1` for the configured Workspace Runtime root.
The runtime intentionally does not read or export the Credential Store, OS keyring,
environment credentials, model directory, application logs, or arbitrary paths
outside the workspace. Provider credentials therefore require separate, explicitly
approved provisioning on the restored installation and are never placed in a
plaintext backup.

Workspace files are user-controlled portable data. A backup is an explicit export,
not a secret vault; users must store the archive with access controls appropriate to
the workspace content.

## Format version 1

The file is a deterministic ZIP container with:

- `manifest.json`, encoded as canonical sorted UTF-8 JSON;
- file bytes under `payload/<portable-relative-path>`;
- fixed member timestamps and ordering;
- SHA-256, byte size, POSIX-compatible permission mode, entry kind and logical owner
  for every file or directory;
- logical root `workspace`, format `linlin-workspace-backup`, and schema version `1`.

Modification timestamps and OS user/group identifiers are deliberately excluded:
they are not portable across Windows, Linux and macOS. Logical ownership and the
portable permission bits are preserved. The same workspace state produces the same
archive bytes on the same supported platform.

Unknown schema versions are rejected. A future version requires an explicit,
reviewed migration path; the runtime never guesses or silently translates formats.

## Validation and security boundaries

The complete archive is validated before the live workspace is touched. Validation
rejects:

- missing, malformed, oversized or unsupported manifests;
- missing, extra, duplicate or case-colliding members;
- checksum or byte-size mismatches;
- absolute, parent-traversal, backslash, drive-qualified, non-NFC or Windows-reserved
  paths;
- symbolic links and filesystem special files;
- undeclared directory hierarchy, entry-count overflow and total-size overflow.

The backup archive itself must be outside the workspace so a restore cannot delete
its own source. Restored paths are rebuilt under a private sibling staging directory
and rechecked before use. No archive-provided path selects a destination.

## Transaction and rollback

Restore uses four bounded steps:

1. Verify the full archive and stage all files.
2. Write a permission-restricted recovery journal in `prepared` state.
3. Atomically rename the current workspace to a rollback directory, then activate the
   staged workspace.
4. Mark `committed`, remove rollback data and delete the journal.

If an operation fails, the original workspace is restored before the error is
returned. If the process terminates between steps, backend startup calls
`PortabilityRuntime.recover_workspace()` with the configured expected root before
importing the API router or any service module that constructs a Workspace Runtime,
and before creating a missing workspace directory. This bootstrap derives the only
allowed staging/rollback names from the validated transaction UUID and either rolls
back an incomplete transaction or finishes cleanup of a committed one. It never
trusts absolute paths from a journal. Non-regular journals and transaction paths fail
closed.

## Rehearsal, RPO and RTO

`rehearse_restore()` performs full verification and staging, then deletes the stage
without changing live data. Both rehearsal and restore return measured elapsed time
as `rto_seconds`. A successfully verified full-workspace archive reports
`rpo_bytes = 0`; content corruption fails closed instead of reporting partial
recovery.

RPO/RTO values are local measurements, not universal service guarantees. Operators
should rehearse with representative workspace size and storage hardware before
setting a commercial service objective.

## Operational rollback

To remove P23, stop callers, run `recover_interrupted()` if a journal exists, and
remove the portability module. Existing workspaces and version-1 archives are not
modified by module removal. Do not manually delete a journal, stage or rollback
directory while recovery is pending.
