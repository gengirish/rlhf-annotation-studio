"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";

import { api } from "@/lib/api";
import { markSessionResolved, useAppStore } from "@/lib/state/store";

/**
 * Populates the app store from the Clerk session.
 *
 * The old login response carried `annotator` and `session_id`, which the
 * dashboard and workspace sync depend on. Clerk's sign-in returns neither, so
 * once Clerk reports a signed-in user we fetch them from `/auth/me`.
 *
 * Without this the dashboard sees an empty store, bounces to sign-in, and the
 * user lands back on the landing page in a loop.
 */
export function ClerkSessionBridge() {
  const { isLoaded, isSignedIn } = useAuth();
  const sessionId = useAppStore((s) => s.sessionId);
  const setAuth = useAppStore((s) => s.setAuth);
  const logout = useAppStore((s) => s.logout);
  const inFlight = useRef(false);

  // Never leave guards waiting forever if Clerk fails to load at all.
  useEffect(() => {
    const timer = setTimeout(markSessionResolved, 8000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!isLoaded) return;

    // Signed out of Clerk but stale local state remains — clear it.
    if (!isSignedIn) {
      if (sessionId) logout();
      markSessionResolved();
      return;
    }

    if (sessionId) {
      markSessionResolved();
      return;
    }
    if (inFlight.current) return;

    inFlight.current = true;
    void (async () => {
      try {
        const me = await api.me();
        setAuth({
          user: {
            id: me.annotator.id,
            name: me.annotator.name,
            email: me.annotator.email,
            phone: me.annotator.phone,
            role: me.annotator.role,
            org_id: me.annotator.org_id
          },
          // The bearer token comes from Clerk per-request; the store only keeps
          // this for legacy call sites that still read it.
          token: "clerk",
          sessionId: me.session_id
        });
      } catch {
        // Leave the store empty; protected routes will send them to sign-in.
      } finally {
        inFlight.current = false;
        markSessionResolved();
      }
    })();
  }, [isLoaded, isSignedIn, sessionId, setAuth, logout]);

  return null;
}
