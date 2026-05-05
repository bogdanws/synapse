import { defineConfig } from '@hey-api/openapi-ts'

// Reads the spec written by `uv run python -m app.scripts.dump_openapi` (run from backend/) and emits a typed client to src/types/api/.
export default defineConfig({
  input: '../backend/openapi.json',
  output: {
    path: 'src/types/api',
    postProcess: ['prettier'],
  },
  plugins: ['@hey-api/client-fetch', '@hey-api/typescript', '@hey-api/sdk'],
})
