import type { NextConfig } from "next";

// Proxy /api → backend: evita CORS e mantém a URL do backend fora do bundle.
// Em docker compose: BACKEND_URL=http://backend:8000; dev local: default abaixo.
const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
