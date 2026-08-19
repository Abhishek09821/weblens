# contracts/

`openapi.json` is the API schema exported from the FastAPI app. It is **generated** — do not edit it
by hand.

```bash
make contracts
```

runs:

1. `backend/scripts/export_openapi.py --out contracts/openapi.json` — builds the app without starting
   a server and dumps its schema with stable key ordering.
2. `npm run gen:api` in `frontend/` — regenerates `frontend/src/types/api.generated.ts` from this file
   via `openapi-typescript`.

## Why it is committed

- The frontend build does not need a running backend.
- Contract changes show up as reviewable diffs in a pull request.
- CI runs `make contracts` and fails if the working tree changes, so backend and frontend types cannot
  drift apart silently.

`api.generated.ts` is the mechanical mirror of this schema. The types the frontend programs against,
plus the zod schemas that validate payloads at runtime, live in `frontend/src/types/analysis.ts`; a
test asserts the two agree. See
[docs/blueprint/08-typescript-models.md](../docs/blueprint/08-typescript-models.md).
