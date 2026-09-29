import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "/app/",
  build: {
    target: "es2018",
  },
  plugins: [vue()],
  test: {
    environment: "jsdom",
  },
  server: {
    host: "0.0.0.0",
    port: 5173
  }
});
