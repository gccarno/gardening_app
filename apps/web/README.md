# Garden Web

React + TypeScript frontend built with Vite.

## Stack

- React 18, TypeScript
- Vite (dev server on port 5173, proxies `/api` to FastAPI on port 8000)
- TanStack Query for data fetching and caching
- React Router for client-side routing

## Dev

```bash
npm install   # first run only
npm run dev   # starts Vite dev server at http://localhost:5173
```

## Build

```bash
npm run build
# Output: dist/ — served by FastAPI as a SPA catch-all in production
```

## Structure

```
src/
├── pages/          # Route-level components (Dashboard, Planner, GardenDetail, …)
├── components/     # Shared UI (ChatWidget, Planner canvas, bed grid, …)
├── hooks/          # TanStack Query hooks wrapping the API client
└── api/            # Typed fetch functions per resource (gardens, beds, plants, …)
```
