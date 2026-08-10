import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

// These values identify the Firebase project publicly and are safe to embed
// in frontend code (unlike the backend's service account key) - Firebase's
// own security model relies on server-side rules/token verification, not on
// keeping this config secret.
const firebaseApp = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
});

// getAuth() validates the API key eagerly and throws synchronously if it's
// missing/malformed - without this try/catch, that exception happens at
// module-import time and takes down the entire app (every screen, not just
// login) with a blank white page and no explanation, since api.js and
// useAuth.js both import `auth`. Degrading to `auth = null` instead lets the
// rest of the app (landing page, etc.) render normally; only the
// login/signup pages need to handle the null case specially.
let auth = null;
try {
  auth = getAuth(firebaseApp);
} catch (err) {
  console.error(
    "Firebase Auth failed to initialize - check VITE_FIREBASE_* values in frontend/.env. " + err.message
  );
}

export { auth };
