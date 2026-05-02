import type { NextConfig } from "next";

/** Cible du proxy Next → API logs S3 (`scripts/run_api.sh`). Docker : `host.docker.internal:8020`. */
const apiProxyTarget = (process.env.FRONTEND_API_PROXY_TARGET ?? "http://127.0.0.1:8020").replace(/\/+$/, "");

/** Proxy Next → API modèle Bedrock (`serve_app`, port 8080). Défaut aligné sur l’instance EC2 ; en local : ``FRONTEND_MODEL_PROXY_TARGET=http://127.0.0.1:8080``. */
const modelProxyTarget = (process.env.FRONTEND_MODEL_PROXY_TARGET ?? "http://13.39.21.85:8080").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      {
        source: "/bff-api/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
      {
        source: "/bff-model/:path*",
        destination: `${modelProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
