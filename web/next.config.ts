import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloudflare Pages serves this app without a Node.js server.
  output: "export",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
