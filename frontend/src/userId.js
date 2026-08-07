const STORAGE_KEY = "expense_tracker_user_id";

// No auth in this MVP - a random ID persisted in localStorage stands in for
// a logged-in user, matching the "session ID" pattern used elsewhere in this
// project. Never sent anywhere except as an opaque key to our own backend.
export function getUserId() {
  let userId = localStorage.getItem(STORAGE_KEY);
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, userId);
  }
  return userId;
}
