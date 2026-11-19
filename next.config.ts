import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The site reads data/*.json and data/players|leagues; the update
  // pipeline's own files (snapshot, ESPN CSVs, download caches, parquet,
  // CSV reports) stay out of the server bundles.
  outputFileTracingExcludes: {
    "/**": [
      "./data/base/**/*",
      "./data/espn/**/*",
      "./data/espn_cache/**/*",
      "./data/cache/**/*",
      "./data/*.csv",
      "./data/*.parquet",
    ],
  },
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
