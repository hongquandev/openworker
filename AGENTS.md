# Repository Guidelines

## Project Structure

- `coworker/`: Python backend, agent engine, permissions, connectors, MCP clients, personas, and FastAPI server.
- `surfaces/gui/src/`: React 18 + TypeScript frontend.
- `surfaces/gui/src-tauri/`: Tauri v2 desktop shell and sidecar lifecycle.
- `stt/`: Rust offline speech-to-text crate.
- `tests/`: Backend pytest suite; `surfaces/gui/src/**/*.test.*` contains frontend unit tests.
- `packaging/`: PyInstaller, installer, DMG, and Windows release tooling.

## Development Commands

Use the repository virtual environment for Python commands.

```bash
bash packaging/setup_dev_env.sh
.venv/bin/pytest
cd surfaces/gui && npm ci
npx tsc --noEmit && npx vitest run
npx playwright test
```

Run locally with `.venv/bin/openworker-server --cwd /path/to/project --port 8765` and `npm run dev` from `surfaces/gui/`. Use `npm run tauri dev` for the full desktop app. Build macOS packages with `bash packaging/build_dmg.sh`.

## Coding Conventions

Python requires 3.10+, future annotations, strict typing, async-first handlers, and Pydantic v2 models. Keep blocking provider/tool work off the event loop. Use `snake_case` for Python, `camelCase` for TypeScript variables/functions, `PascalCase` for React components, and Rust standard formatting/conventions. Keep frontend API calls in `surfaces/gui/src/api.ts` and components under `surfaces/gui/src/components/`.

## Testing

Name backend tests `tests/test_<area>.py` and frontend tests `<Component>.test.tsx` or `<feature>.test.ts`. Run focused tests while iterating, then run the full backend and frontend suites before submitting. Add regression coverage for permission, approval, connector, lifecycle, and serialization changes.

## Security and Architecture

Never weaken hard permission floors, approval gates, audit provenance, origin checks, or path scoping. Preserve `_exit_when_orphaned()` and Tauri sidecar supervision. Do not bundle AGPL dependencies; use `pypdf`/`pypdfium2` for PDF support. Keep MCP constrained to `>=1.28.1,<2` and ship PyInstaller in onedir mode.

## Commits and Pull Requests

Use concise imperative commit subjects, preferably scoped by area, such as `fix(server): preserve approval provenance`. PRs should explain the behavior change, link the relevant issue/spec, list verification commands, and include screenshots or recordings for UI changes. Keep unrelated refactors out of feature PRs.

## Browser Automation with playwright-cli

Use `playwright-cli` to inspect, automate, and verify frontend flows such as Inbox approval cards, session turns, and settings screens.

### Common Workflow

1. Open the local GUI (e.g. Inbox or Chat):
   ```bash
   playwright-cli open http://localhost:1420/#/inbox
   ```

2. Inspect elements and snapshot the accessibility tree:
   ```bash
   playwright-cli snapshot
   playwright-cli find "Allow once"
   ```

3. Interact using snapshot element references (e.g. `e12`):
   ```bash
   playwright-cli click e12
   playwright-cli fill e5 "Search query" --submit
   ```

4. Verify UI state and capture artifacts:
   ```bash
   playwright-cli screenshot --filename=approval_state.png
   playwright-cli console
   ```

5. Clean up browser sessions:
   ```bash
   playwright-cli close
   ```

