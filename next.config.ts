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
      // Pipeline-only JSON; the site reads index, boards, coverage and leagues.
      "./data/espn_history.json",
      "./data/espn_probe.json",
      "./data/images.json",
      "./data/live_matches.json",
      "./data/source_totals.json",
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
