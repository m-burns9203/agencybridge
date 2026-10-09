// File: main.tsx
// Description: Mounts the AgencyBridge React application in the browser.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: react, react-dom, App.tsx, styles.css

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

// The ! tells TypeScript the root element exists; index.html supplies it.
createRoot(document.getElementById("root")!).render(
  <StrictMode><App /></StrictMode>,
);
