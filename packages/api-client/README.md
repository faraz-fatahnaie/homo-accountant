# @arya/api-client — typed API client

Generated from the FastAPI **OpenAPI** contract so the frontend can never drift from the
backend. Strategy:

1. **Contract source:** `GET /openapi.json` from the running API (FastAPI generates it).
2. **Generation:** `openapi-typescript` produces `src/schema.d.ts` (all path/param/response
   types), then `scripts/build-client.mjs` emits typed fetch helpers per endpoint that reuse
   the types from `apps/web/src/lib/api.ts` conventions (error envelope, bearer auth).
3. **CI drift guard:** `ci.yml` regenerates and fails on any diff (`git diff --exit-code`).

**Status:** scaffolded in slice 1. Real generation lands in slice 2, when the first stable
domain endpoints (ledger/contacts) exist — generation against the current auth contract will
be wired then. Until then `apps/web/src/lib/api.ts` is the hand-kept contract mirror.
