# Client architecture

`frontend/src` is the single React/Vite UI source of truth. The Tauri project
under `desktop/src-tauri` is only the native shell and integration boundary.
Its development and build commands invoke the frontend package and consume
`frontend/dist`; `desktop/src` is legacy, inactive source retained temporarily
for non-destructive migration history and must not receive new UI work.

The UI calls the backend through `frontend/src/api.ts`. Production or packaged
environments set `VITE_API_BASE_URL`; browser development uses the relative
`/api` path and Vite's configurable `LINLIN_BACKEND_URL` proxy. No credential,
workspace, provider, or tool runtime logic belongs in either browser or Tauri
shell code.
