# ValueX Client

This folder contains the frontend for the ValueX prototype. It is a React 19 + Vite application with two main surfaces:

- a landing page that explains the current prototype scope
- a chat interface for portfolio-health questions backed by the ValueX API

The client is intentionally honest about the current product state. It presents a polished UI, but the implemented workflow today is centered on portfolio-health analysis rather than live brokerage integrations or automated monitoring.

## Stack

- React 19
- TypeScript
- Vite
- React Router
- Tailwind CSS
- Radix UI primitives and shadcn-style components
- Framer Motion

## Running Locally

Install dependencies:

```bash
npm install
```

Create a local env file in this directory:

```bash
VITE_API_URL=http://127.0.0.1:8000

```

Start the dev server:

```bash
npm run dev
```

By default the Vite dev server runs on port `3000`.

## API Configuration

The client reads the backend origin from `VITE_API_URL`.

- in local development, point it at your backend, for example `http://127.0.0.1:8000`
- in production, set `VITE_API_URL` in your hosting provider so the built client calls the deployed API directly
- the backend routes are used as-is, for example `/chat`, `/users`, `/user-summary`, and `/health`

Examples:

- `/chat` -> `${VITE_API_URL}/chat`
- `/users` -> `${VITE_API_URL}/users`
- `/user-summary` -> `${VITE_API_URL}/user-summary`
- `/health` -> `${VITE_API_URL}/health`

## Available Scripts

- `npm run dev`: start the Vite dev server
- `npm run build`: run TypeScript build checks and create a production bundle
- `npm run preview`: preview the production build locally
- `npm run lint`: run ESLint across the client

## Project Structure

- `src/pages`: route-level screens
- `src/sections`: landing page sections
- `src/components`: reusable UI and visual components
- `src/components/ui`: shared design-system style components
- `src/lib/chat.ts`: SSE chat client and event parsing
- `src/lib/utils.ts`: shared utility helpers
- `src/hooks`: custom hooks

## Routes

- `/`: marketing and product overview page
- `/chat`: streaming chat interface for asking questions against fixture users

## Chat Flow

The chat page currently does the following:

- loads sample users from `/users`
- loads a summary for the selected user from `/user-summary`
- sends chat requests to `/chat`
- consumes server-sent events for progress, message, metrics, error, and done states
- keeps a session id in the client so follow-up questions stay in the same conversation

The SSE parsing lives in `src/lib/chat.ts` and is designed around the backend event model used by this repo.

## TypeScript Setup

This client uses a single [tsconfig.json](tsconfig.json) for both app code and the Vite config.

It includes:

- browser libraries for React UI code
- Node types for `vite.config.ts`
- the `@/*` alias mapped to `src/*`

This is simpler than the split Vite starter setup and is enough for the current project size.

## Current Scope

What this client reflects today:

- portfolio-health focused product messaging
- fixture-user driven chat flows
- benchmark and portfolio-health oriented analysis UI
- a frontend designed to match the implemented backend rather than a hypothetical future roadmap

What it does not claim:

- live brokerage connectivity
- trade execution
- background account monitoring
- real-time alerting

## Build Notes

The client currently builds successfully, but production bundling still reports a large chunk warning related to the globe/3D experience. That warning does not block the build, but it is a good future optimization target.
