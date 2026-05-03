import type { NextConfig } from "next";
import { getBackendBaseUrl } from "./src/lib/apiBackendUrl";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const base = getBackendBaseUrl();
    return [
      {
        source: "/api/v1/:path*",
        destination: `${base}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
