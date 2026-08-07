const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, { method = "GET", body, params } = {}) {
  const url = new URL(path, BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }

  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const error = new Error(detail?.detail || `Request failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export const api = {
  getConfig: () => request("/config"),

  createLinkToken: (userId) => request("/link/token", { method: "POST", body: { user_id: userId } }),

  exchangePublicToken: (userId, publicToken) =>
    request("/link/exchange", { method: "POST", body: { user_id: userId, public_token: publicToken } }),

  sync: (userId) => request("/sync", { method: "POST", body: { user_id: userId } }),

  getTransactions: (userId, { startDate, endDate, category } = {}) =>
    request("/transactions", {
      params: { user_id: userId, start_date: startDate, end_date: endDate, category },
    }),

  getBudgetStatus: (userId, { startDate, endDate } = {}) =>
    request("/budget/status", { params: { user_id: userId, start_date: startDate, end_date: endDate } }),

  setBudget: (userId, category, amount) =>
    request("/budget", { method: "POST", body: { user_id: userId, category, amount } }),
};
