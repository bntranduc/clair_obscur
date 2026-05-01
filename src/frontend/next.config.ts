import type { NextConfig } from "next";

/** Cible du proxy (serveur Next → uvicorn dashboard). Surcharge en Docker : `host.docker.internal:8010`. */
const dashboardProxyTarget = (process.env.DASHBOARD_API_PROXY_TARGET ?? "http://127.0.0.1:8010").replace(
  /\/+$/,
  ""
);

const nextConfig: NextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      {
        source: "/bff-dashboard/:path*",
        destination: `${dashboardProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
