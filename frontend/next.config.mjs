/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Don't advertise the framework/version to attackers scanning for known CVEs.
  poweredByHeader: false,
  experimental: {
    typedRoutes: true
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // The app is never meant to be framed; blocks clickjacking.
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()"
          }
        ]
      }
    ];
  }
};

export default nextConfig;
