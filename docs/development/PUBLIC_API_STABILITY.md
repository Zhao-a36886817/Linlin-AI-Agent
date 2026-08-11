# Linlin Agent Public and Plugin API Stability

## Published public API contract

Linlin Agent's current public HTTP contract is version `1`. Existing clients remain
compatible: omitting `X-Linlin-API-Version` selects version `1`. Clients should send
`X-Linlin-API-Version: 1` so future migrations are explicit.

Every `/api` response, including validation and negotiation errors, publishes:

- `X-Linlin-API-Version: 1`
- `X-Linlin-API-Stability: stable`
- `Vary: X-Linlin-API-Version`

An unsupported requested version receives HTTP `406` and a safe JSON response listing
the supported versions. No URL or version-translation shim is introduced.

## Inventory and ownership

| Route family | Contract owner |
| --- | --- |
| `/api/health`, `/api/system/*` | Platform API |
| `/api/agents/*` | Agent Runtime |
| `/api/providers/*`, `/api/models/*` | Provider Runtime |
| `/api/chat/*` | Chat Runtime |
| `/api/code-generation/*` | Code Generation |
| `/api/training/*` | Training Runtime |
| `/api/runtime-control/*` | Runtime Control |
| `/api/advanced-runtime/*` | Advanced Runtime |

The ownership map is also encoded in `app.api.contracts`. An automated OpenAPI test
fails when a new public route has no owner.

## Compatibility and semantic versioning

The application release follows semantic versioning. Within a public API major
contract:

- Patch releases may fix behavior without changing documented request or response
  meaning.
- Minor releases may add optional fields or endpoints. Clients must ignore unknown
  response fields.
- Removing or renaming a route or field, making an optional field required, changing
  its type or meaning, or weakening a security boundary is breaking and requires a new
  major API contract plus a documented migration.

Security checks, credential isolation, workspace controls, and provider/tool runtime
boundaries are never bypassed for compatibility.

## Deprecation policy

A stable contract element must remain available for at least two minor releases and
90 days after its deprecation notice, whichever is longer. A deprecated HTTP element
must publish `Deprecation`, `Sunset`, and a `Link` to its migration documentation.
Removal requires a major contract version and compatibility tests. There are no
deprecated public elements in version `1` today.

## Plugin contract

The public plugin declaration contract uses manifest schema version `1` and SDK
version `1`. A plugin has its own strict `MAJOR.MINOR.PATCH` version. Unknown schema or
SDK versions and unknown capabilities are rejected during validation; Linlin Agent
does not silently load, translate, or execute incompatible plugin code. Permission
approval remains separate from compatibility.

## Migration and rollback

The existing unversioned `/api` URL is the version `1` contract and needs no client
payload migration. Clients can migrate incrementally by adding the request header.
Rollback consists of removing negotiation middleware and response-header exposure;
the underlying routes and payloads remain unchanged.
