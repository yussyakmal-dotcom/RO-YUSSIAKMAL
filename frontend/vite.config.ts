import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Assets are collected by Django and served from the existing port 900.
  base: "/static/frontend/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:900",
      "/admin": "http://127.0.0.1:900",
    },
  },
});
