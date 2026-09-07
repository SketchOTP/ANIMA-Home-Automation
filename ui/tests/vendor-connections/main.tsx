import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { VendorConnectionsPanel } from "../../src/VendorConnectionsPanel";
import "../../src/styles.css";

function Fixture() {
  const [visible, setVisible] = useState(true);
  const [expired, setExpired] = useState(false);
  return <main className="content" style={{ margin: "0 auto" }}>
    <h1>Synthetic UI fixture</h1><p>Declared mock responses only — not live device evidence.</p>
    <label>Fixture theme <select defaultValue="night" onChange={event => { document.documentElement.dataset.appearance = event.target.value; }}>
      <option value="night">Night</option><option value="light">Light</option><option value="system">System</option>
    </select></label>
    <button onClick={() => setVisible(value => !value)}>{visible ? "Hide fixture panel" : "Show fixture panel"}</button>
    {expired ? <p role="alert">Fixture session expired; protected panel removed.</p> : visible && <VendorConnectionsPanel onAuthFailure={() => setExpired(true)} />}
  </main>;
}
createRoot(document.getElementById("root")!).render(<StrictMode><Fixture /></StrictMode>);
