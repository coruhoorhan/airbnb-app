import L from "leaflet";
if (typeof window !== "undefined") { window.L = L; }


let globalCsrfToken = "";

const originalFetch = window.fetch;
window.fetch = async (...args) => {
  let [resource, config] = args;

  let urlStr = typeof resource === 'string' ? resource : (resource instanceof Request ? resource.url : "");

  if (urlStr.includes('/api/')) {
    config = config || {};
    config.credentials = 'include';

    const method = config.method ? config.method.toUpperCase() : 'GET';
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      if (globalCsrfToken) {
        config.headers = {
          ...config.headers,
          'x-csrf-token': globalCsrfToken
        };
      }
    }

    if (typeof resource === 'string') {
      args[1] = config;
    } else if (resource instanceof Request) {
      args[0] = new Request(resource, config);
    }
  }

  const response = await originalFetch(...args);

  // If the server rotates the token and sends it back in a header or we just called /api/auth/csrf
  const newCsrf = response.headers.get('x-csrf-token');
  if (newCsrf) {
    globalCsrfToken = newCsrf;
  }

  return response;
};

// Fetch initial CSRF token
originalFetch('/api/auth/csrf', {credentials: 'include'})
  .then(res => res.json())
  .then(data => {
    if (data.success && data.csrfToken) {
      globalCsrfToken = data.csrfToken;
    }
  })
  .catch(console.error);

import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
