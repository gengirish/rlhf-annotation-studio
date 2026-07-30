import type { MetadataRoute } from "next";

/**
 * Keep the authenticated app out of search results. The paths here mirror the
 * protected prefixes in `src/middleware.ts` — update both together.
 *
 * The landing page, /auth, and /certificate/* stay crawlable: certificates are
 * meant to be shared publicly.
 */
const DISALLOWED = [
  "/dashboard",
  "/analytics",
  "/auto-reviews",
  "/reviews",
  "/settings",
  "/author",
  "/team",
  "/quality",
  "/datasets",
  "/audit",
  "/webhooks",
  "/task",
  "/exams",
  "/certificates",
  "/course"
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: DISALLOWED.map((path) => `${path}/`)
    }
  };
}
