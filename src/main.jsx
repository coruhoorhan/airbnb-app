

const originalFetch = window.fetch;
window.fetch = async (...args) => {
  let [resource, config] = args;

  let urlStr = typeof resource === 'string' ? resource : (resource instanceof Request ? resource.url : "");

  if (urlStr.includes('/api/')) {
    config = config || {};
    config.credentials = 'include';

    const method = config.method ? config.method.toUpperCase() : 'GET';
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      const csrfToken = document.cookie.split('; ').find(row => row.startsWith('csrfToken='))?.split('=')[1];
      if (csrfToken) {
        config.headers = {
          ...config.headers,
          'x-csrf-token': csrfToken
        };
      }
    }

    if (typeof resource === 'string') {
      args[1] = config;
    } else if (resource instanceof Request) {
      args[0] = new Request(resource, config);
    }
  }
  return originalFetch(...args);
};


// Fetch initial CSRF token
originalFetch('/api/auth/csrf', {credentials: 'include'}).catch(console.error);

import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
