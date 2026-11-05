import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import ProductionApp from "./ProductionApp";
import "./styles.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element is missing");
}

createRoot(rootElement).render(
  <React.StrictMode>
    {window.location.pathname.startsWith("/produksi/") ? <ProductionApp /> : <App />}
  </React.StrictMode>,
);
