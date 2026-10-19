import React from "react";
import ReactDOM from "react-dom/client";
import { keycloak } from "./auth";
import { App } from "./App";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root")!);

keycloak
  .init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false })
  .then(() => root.render(<React.StrictMode><App /></React.StrictMode>))
  .catch(() =>
    root.render(
      <div className="boot-error">
        Could not reach the sign-in service. Check that Keycloak is running on port 8080.
      </div>,
    ),
  );
