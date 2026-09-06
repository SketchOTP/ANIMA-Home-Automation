# Goal increment — commissioned device lifecycle

ANIMA’s Devices view now covers the next bounded management-plane step after
commissioning. An owner can rename a commissioned device, move it between
already-commissioned rooms or zones, and retire it from ANIMA’s canonical
household model without opening Home Assistant.

## Authority boundary

The browser sends only a canonical resource reference and the requested
semantic change. The Core gateway routes the operation through the existing
Home Assistant plugin and policy boundary. The plugin verifies that the
resource and destination belong to the authenticated household. No provider
host, entity ID, service name, token, or arbitrary registry payload is
accepted from the browser.

Rename preserves the former name as a Graph alias. Reassignment retires the
old `INSTALLED_IN` edge and appends a new one with an audit event. Retirement
removes the canonical resource’s active semantic edges, provider references,
Truth bindings, aliases, and capabilities from the active model. It does not
delete or mutate the Home Assistant registry object.

## Validation

- The focused Home Assistant/plugin, Graph, and UI API tests pass.
- Full Python pytest passes.
- Ruff passes for the changed Python scope.
- TypeScript check and the production Vite build pass using the bundled
  workspace runtime.
- `git diff --check` passes.

This is a bounded implementation increment within goal-wide management-plane
convergence. It is not Phase 15 work and does not accept the pending alert
policy packet or the permanent project goal.
