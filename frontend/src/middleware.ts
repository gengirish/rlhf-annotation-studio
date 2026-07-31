import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// NOTE: this file must stay named `middleware.ts`. Next.js only renamed the
// convention to `proxy.ts` in v16; this app is on 15.x, where a `proxy.ts`
// would be silently ignored and every route below would be left unprotected.

// Mirrors the disallow list in src/app/robots.ts — update both together.
const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/analytics(.*)",
  "/auto-reviews(.*)",
  "/reviews(.*)",
  "/settings(.*)",
  "/author(.*)",
  "/team(.*)",
  "/quality(.*)",
  "/datasets(.*)",
  "/audit(.*)",
  "/webhooks(.*)",
  "/task(.*)",
  "/exams(.*)",
  "/certificates(.*)",
  "/course(.*)"
]);

export default clerkMiddleware(async (auth, request) => {
  if (!isProtectedRoute(request)) return;

  // `auth.protect()` renders a 404 for signed-out users, which reads as a broken
  // link rather than "please sign in". Redirect instead, and send them back to
  // the page they asked for once authenticated.
  const { userId, redirectToSignIn } = await auth();
  if (!userId) {
    return redirectToSignIn({ returnBackUrl: request.url });
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and static assets, but run on everything else.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Clerk's auto-proxy path.
    "/__clerk/:path*",
    "/(api|trpc)(.*)"
  ]
};
