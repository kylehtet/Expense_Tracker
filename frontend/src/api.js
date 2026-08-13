import axios from "axios";
import { auth } from "./firebase";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Every request carries the current Firebase ID token, if there is one -
// getIdToken() returns the cached token and transparently refreshes it
// in the background when it's close to expiring, so this never needs to
// think about token lifetimes itself.
client.interceptors.request.use(async (config) => {
  const user = auth?.currentUser;
  if (user) {
    const token = await user.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

async function request(path, { method = "GET", body, params } = {}) {
  try {
    const response = await client.request({ url: path, method, data: body, params });
    return response.data;
  } catch (err) {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    const error = new Error(detail || `Request failed: ${status ?? "network error"}`);
    error.status = status;
    throw error;
  }
}

export const api = {
  getConfig: () => request("/config"),

  getMe: () => request("/auth/me"),

  createLinkToken: () => request("/link/token", { method: "POST" }),

  exchangePublicToken: (publicToken) =>
    request("/link/exchange", { method: "POST", body: { public_token: publicToken } }),

  disconnect: () => request("/link/disconnect", { method: "POST" }),

  sync: () => request("/sync", { method: "POST" }),

  getTransactions: ({ startDate, endDate, category } = {}) =>
    request("/transactions", { params: { start_date: startDate, end_date: endDate, category } }),

  getBudgetStatus: ({ startDate, endDate } = {}) =>
    request("/budget/status", { params: { start_date: startDate, end_date: endDate } }),

  setBudget: (category, amount) => request("/budget", { method: "POST", body: { category, amount } }),

  recommendBudgets: (months = 6) => request("/budget/recommend", { method: "POST", body: { months } }),

  getGoals: (status = "active") => request("/goals", { params: { status } }),

  createGoal: ({ name, targetAmount, category, targetDate, currentSaved }) =>
    request("/goals", {
      method: "POST",
      body: { name, target_amount: targetAmount, category, target_date: targetDate, current_saved: currentSaved },
    }),

  updateGoal: (goalId, fields) => request(`/goals/${goalId}`, { method: "PATCH", body: fields }),

  abandonGoal: (goalId) => request(`/goals/${goalId}`, { method: "DELETE" }),

  getGoalHealth: (goalId) => request(`/goals/${goalId}/health`),

  getAutoBudget: (goalId, location) => request(`/goals/${goalId}/auto-budget`, { params: { location: location || undefined } }),

  getRecurring: () => request("/recurring"),
};
