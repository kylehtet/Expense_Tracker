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
  const [refreshTick, setRefreshTick] = useState(0);

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

  // emailVerified can flip to true without a new auth-state event - the user
  // clicks the link Firebase emailed them in a different tab, this tab never
  // hears about it. Re-checking on focus (reload() mutates the same `user`
  // object in place) plus a tick bump to force the re-render is enough for
  // the "verify your email" banner to clear itself on its own.
  useEffect(() => {
    if (!auth) return;
    const recheck = async () => {
      if (!auth.currentUser) return;
      await auth.currentUser.reload();
      setRefreshTick((n) => n + 1);
    };
    window.addEventListener("focus", recheck);
    return () => window.removeEventListener("focus", recheck);
  }, []);

  return {
    user,
    loading,
    isAuthenticated: !!user,
    userId: user?.uid,
    emailVerified: user?.emailVerified ?? true,
    _refreshTick: refreshTick,
  };
}
