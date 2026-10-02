import { useState } from "react";
import { createRoot } from "react-dom/client";
import { InitiativePanel } from "../../src/InitiativePanel";
import { RingConnectionPanel } from "../../src/RingConnectionPanel";
import { HouseholdSituationPanel } from "../../src/HouseholdSituationPanel";
import "../../src/styles.css";

document.documentElement.dataset.theme = "night";
document.documentElement.dataset.accent = "purple";
function Fixture() {
  const [expired, setExpired] = useState(false);
  const ring = new URLSearchParams(location.search).get("panel") === "ring";
  const situation = new URLSearchParams(location.search).get("panel") === "situation";
  const mutate = async (path: string, payload?: Record<string, unknown>) => {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Anima-CSRF": "synthetic-test-csrf" }, body: JSON.stringify({ payload }) });
    if (response.status === 401) setExpired(true);
    return response.ok ? response.json() : null;
  };
  return <main style={{ maxWidth: 1280, margin: "0 auto", padding: 20 }}>
    <h1>Synthetic browser fixture · not live household or Ring data</h1>
    {expired && <p role="alert">Fixture session expired</p>}
    {ring ? <RingConnectionPanel csrfToken="synthetic-test-csrf" onAuthFailure={() => setExpired(true)} /> : situation ? <HouseholdSituationPanel mutate={mutate} onAuthFailure={() => setExpired(true)} readOnly={new URLSearchParams(location.search).has("readonly")} /> : <InitiativePanel onAuthFailure={() => setExpired(true)} mutate={mutate} />}
  </main>;
}
createRoot(document.getElementById("root")!).render(<Fixture />);
