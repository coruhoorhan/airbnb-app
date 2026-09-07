let currentAuthToken = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
let currentCsrfToken = typeof window !== "undefined" ? localStorage.getItem("csrf_token") : null;

export async function syncAuthSession(userOrEmail) {
  try {
    const email = typeof userOrEmail === "string" 
      ? userOrEmail 
      : (userOrEmail?.email || "guest@fatsa.bel.tr");

    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
      credentials: "include"
    });
    const data = await res.json();
    if (data.success && data.token) {
      currentAuthToken = data.token;
      currentCsrfToken = data.csrfToken || data.token;
      if (typeof window !== "undefined") {
        localStorage.setItem("auth_token", data.token);
        if (data.csrfToken) localStorage.setItem("csrf_token", data.csrfToken);
      }
      return data;
    }
  } catch (err) {
    console.error("Auth session sync failed:", err);
  }
}

export function getAuthToken() {
  return currentAuthToken || (typeof window !== "undefined" ? localStorage.getItem("auth_token") : null);
}

export function getCsrfToken() {
  return currentCsrfToken || (typeof window !== "undefined" ? localStorage.getItem("csrf_token") : null);
}

export async function apiFetch(url, options = {}) {
  const token = getAuthToken();
  const csrf = getCsrfToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (csrf && !headers["x-csrf-token"]) {
    headers["x-csrf-token"] = csrf;
  }

  const opts = {
    ...options,
    headers,
    credentials: "include"
  };

  let res = await fetch(url, opts);

  // If unauthorized, auto-heal session once and retry
  if (res.status === 401) {
    await syncAuthSession("guest@fatsa.bel.tr");
    const retryToken = getAuthToken();
    if (retryToken) {
      headers["Authorization"] = `Bearer ${retryToken}`;
      const retryCsrf = getCsrfToken();
      if (retryCsrf) headers["x-csrf-token"] = retryCsrf;
      res = await fetch(url, { ...options, headers, credentials: "include" });
    }
  }

  return res;
}
