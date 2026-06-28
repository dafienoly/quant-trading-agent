# AgentOps Web Validation

This document defines the current validation path for `apps/web`.

## Local checks

Run these commands from the repository root:

```bash
cd apps/web
npm run test
npm run build
```

Then return to the repository root and run the repository checks:

```bash
cd ../..
python -m pytest tests/test_web_frontend_validation.py -q
python scripts/validate_pr_reports.py --base origin/main --head HEAD --strict --json
git diff --check
```

## Validated surface

The repository-level validation checks that:

1. the web workspace exists;
2. the expected TypeScript, Vite, API, selector, and component files exist;
3. package scripts expose `test` and `build`;
4. the build script includes TypeScript checking and Vite build;
5. generated dependency directories are not committed.

## Current boundary

This validation path is intentionally local and read-only. It does not add a new workflow file in this slice. A dedicated frontend workflow and dependency lock can be added later after the current product surface is stable.

## Result

PASS_WITH_NOTES
