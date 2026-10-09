// File: vite.config.ts
// Description: Forwards local API requests from Vite to the Python server.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: vite

import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    // React requests /api/cases on its own origin. Vite forwards that request
    // to FastAPI, so local development needs no separate CORS configuration.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
