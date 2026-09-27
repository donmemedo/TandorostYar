import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  rewrites: async () => [{ source: "/api/:path*", destination: `${process.env.BACKEND_URL ?? "http://localhost:8330"}/api/:path*` }],
};

export default config;
