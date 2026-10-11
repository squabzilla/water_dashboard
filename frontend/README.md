# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.


# Frontend

React + TypeScript app, built with Vite. Source code lives in `src/`.

## Development workflow

Three processes run at the same time, each in its own terminal so their logs stay separate:

| Process | Command | Port |
| --- | --- | --- |
| PostGIS (Docker) | start via the Makefile | 5433 |
| FastAPI (uvicorn) | `uv run uvicorn backend.backend_main:app --reload --reload-dir backend --reload-dir data_pipeline` (from the project root) | 8000 |
| Vite dev server | `npm run dev` (from `frontend/`) | 5173 |

Open `http://localhost:5173` in the browser.

### Why `--reload-dir` is required

Without it, uvicorn's auto-reloader watches the whole project root, including `Docker/postgres_data_folder`. That folder is owned by the Postgres container and is unreadable to the host user, so the file watcher crashes with a permission error. Watching only source directories avoids the problem.

## How the frontend reaches the API (the Vite proxy)

The page is served from `http://localhost:5173`, and the API from `http://127.0.0.1:8000`. Different ports (and hosts) are different origins, so the browser blocks the frontend's JavaScript from reading the API's responses (CORS). The server still answers `200`; the browser discards the response.

`vite.config.ts` solves this for development:

```ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8000'
  }
}
```

The browser only talks to the Vite server, which forwards any `/api` request to FastAPI. That forwarding is server-to-server, so the same-origin policy never applies. Frontend code uses relative URLs (`/api/summary`), and `API_BASE_URL` in `src/config/apiConfig.ts` is an empty string.

Production works the same way in principle: a reverse proxy (nginx or Caddy) serves the built frontend files and forwards `/api` to FastAPI, so the browser again sees a single origin. Relative URLs mean the frontend code does not change between environments.

If the backend is not running, the browser receives a `500` for `/api/...` requests and the Vite terminal logs a connection-refused error. That failure looks nothing like a CORS error.

## Dev, build, and preview

| Command | What it does | Use it for |
| --- | --- | --- |
| `npm run dev` | Serves source files on demand with hot reload. No build step. | Daily work |
| `npm run build` | Type-checks, compiles, bundles, minifies, and fingerprints filenames into `dist/`. | Producing the production files |
| `npm run preview` | Serves what is already in `dist/`. Does **not** build. | Checking a build locally |

- `preview` serves a stale `dist/` without warning, and fails if `dist/` does not exist. Run `npm run build` first, every time.
- `preview` inherits `server.proxy` by default, so the proxy above also applies to it.
- `preview` is not a production server. Production runs no Node process at all: `dist/` is a folder of static files served by the reverse proxy.

Recommended habit: use `npm run dev` for everyday changes, and run `npm run build && npm run preview` at milestones, before deploying, and whenever something behaves oddly. Differences that only show up in a build include TypeScript errors that dev mode tolerates, minification and chunking problems, and `StrictMode`'s double-running of effects (dev only).

## Setup on a new machine

`node_modules/` is gitignored and must be rebuilt on each machine:

```bash
cd frontend
npm ci
```

`npm ci` installs exactly the versions in `package-lock.json` and fails if the lockfile is missing or out of sync with `package.json`. Use `npm install <package>` only when adding a dependency, which updates the lockfile.

The project was scaffolded once with `npm create vite@latest frontend -- --template react-ts`. The result is committed, so this command is never re-run.