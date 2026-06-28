# V16.1 Web Foundation Design

## Goal

Add a minimal frontend foundation for the AgentOps page.

## Scope

The new web app is placed under `apps/web`. It uses React, Vite, and TypeScript.

## Readonly data

The page reads AgentOps summary, stage profile, and quality overview from existing product APIs.

## States

The page has loading, ready, and error states.

## Non-goals

No trading page migration. No write action. No broker, account, or order integration.

## Next

Future PRs can add routing, details page, E2E, and CI build checks.