import type { Route } from "next";
import { redirect } from "next/navigation";

/**
 * The email/password form that lived here was replaced by Clerk. The route is
 * kept as a redirect because it is linked from older emails and bookmarks, and
 * was the historical target of the API client's 401 handler.
 */
export default function LegacyAuthPage() {
  // typedRoutes cannot infer the optional catch-all `/sign-in/[[...sign-in]]`
  // from a bare literal, so the target is asserted.
  redirect("/sign-in" as Route);
}
