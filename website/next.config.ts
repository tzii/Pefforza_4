import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'export',
  // Keep the single-page export at index.html. Vinext's route basePath skips
  // prerendering /; an absolute asset prefix also preserves the disk layout.
  assetPrefix:
    process.env.PEFFORZA_PAGES === '1'
      ? process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, '')
      : undefined,
};

export default nextConfig;
