import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  images: { unoptimized: true }, // no <Image> is used; this also switches the /_next/image proxy (an SSRF surface) off
  // Used by `npm run dev`, and when the frontend is reached without the Caddy edge. Production traffic for /api goes straight to the backend at the edge.
  rewrites: async () => [{ source: "/api/:path*", destination: `${process.env.BACKEND_URL ?? "http://localhost:8330"}/api/:path*` }],
  headers: async () => [{
    source: "/:path*",
    headers: [
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
      { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    ],
  }],
};

export default config;
