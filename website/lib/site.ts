const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://tzii.github.io/Pefforza_4/';

export const publicAsset = (path: string) => `${basePath}${path}`;
