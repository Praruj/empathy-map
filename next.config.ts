import type { NextConfig } from "next";

// GitHub Pages serves project sites from /<repo-name>. The workflow sets
// NEXT_PUBLIC_BASE_PATH=/empathy-map; locally it is empty.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  // The Next.js image optimizer needs a server; Pages is static.
  images: { unoptimized: true },
};

export default nextConfig;
