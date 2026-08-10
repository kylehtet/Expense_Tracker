import { useEffect, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "./firebase";

// Wraps Firebase's own auth-state listener so the rest of the app can just
// read { user, loading, isAuthenticated } instead of touching the SDK
// directly. api.js separately calls auth.currentUser.getIdToken() per
// request - Firebase handles token refresh internally either way.
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }
    return onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });
  }, []);

  return { user, loading, isAuthenticated: !!user, userId: user?.uid };
}
