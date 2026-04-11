import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/analytics",
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
];

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!isProtectedPath(pathname)) {
    return NextResponse.next();
  }

  const hasSessionCookie = Boolean(request.cookies.get("rlhf_session")?.value);
  if (hasSessionCookie) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/auth";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/dashboard",
    "/analytics",
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
    "/dashboard/:path*",
    "/analytics/:path*",
    "/reviews/:path*",
    "/settings/:path*",
    "/author/:path*",
    "/team/:path*",
    "/quality/:path*",
    "/datasets/:path*",
    "/audit/:path*",
    "/webhooks/:path*",
    "/task/:path*",
    "/exams/:path*",
  ],
};
