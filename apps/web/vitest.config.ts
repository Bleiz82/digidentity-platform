import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  esbuild: {
    // New JSX transform — auto-imports react/jsx-runtime, no manual React import needed
    jsx: "automatic",
    jsxImportSource: "react",
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
