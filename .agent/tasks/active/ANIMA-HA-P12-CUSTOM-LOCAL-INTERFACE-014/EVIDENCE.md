# Evidence ledger

## Established locally

- Locked Python dependency synchronization, backend formatting/type checks, deterministic API tests, Node dependency lock/install, TypeScript checks, UI unit checks, Vite build, package build, Compose config, and Playwright desktop/tablet/phone scenarios have been exercised during this task.
- The deterministic UI harness covers public health, unauthorized reads, test OAuth mapping, semantic bootstrap, CSRF/origin rejection, conversation ingress, and absence of internal row values.
- Browser tests cover responsive navigation, dashboard rendering, conversation route, same-origin network behavior, browser-storage absence, and task/capability views.
- Implementation checkpoint `8a8f798d5d2319e690572d69a323e10459924bce` is pushed; hosted CI `33572829176` passed on that exact SHA. An earlier CI run `33572285917` failed only at strict-mypy test typing and was corrected in the published fix.

## Not established by deterministic tests

- Real Home Assistant OAuth consent/token exchange.
- Native Raspberry Pi deployment.
- A host composition root injecting the existing production journal/attention/context/AgentRuntime and Phase 5/4/9 command bridges into this API.
- Live user/household commissioning.

## Publication pending

- Final governed SHA/CI and Notion readback are intentionally not recorded until the governance-only closure commit is created and its exact hosted CI succeeds.

Claims remain classified as implemented/tested/unknown rather than promoted to production evidence.
