import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const basePath = (process.env.PAGES_BASE_PATH ?? '/Pefforza_4').replace(
  /\/$/,
  '',
);
if (basePath && (!basePath.startsWith('/') || basePath.includes('..'))) {
  throw new Error('PAGES_BASE_PATH must be an absolute URL path without ..');
}
const env = {
  ...process.env,
  PEFFORZA_PAGES: '1',
  NEXT_PUBLIC_BASE_PATH: basePath,
  NEXT_PUBLIC_SITE_URL:
    process.env.PAGES_SITE_URL ?? 'https://tzii.github.io/Pefforza_4/',
};
const site = new URL(env.NEXT_PUBLIC_SITE_URL);
if (
  site.pathname.replace(/\/$/, '') !== basePath ||
  !site.pathname.endsWith('/')
) {
  throw new Error('PAGES_SITE_URL must end in PAGES_BASE_PATH followed by /');
}

for (const script of [
  '../node_modules/vinext/dist/cli.js',
  './verify-build.mjs',
]) {
  const args = script.includes('vinext') ? ['build'] : [];
  const result = spawnSync(
    process.execPath,
    [fileURLToPath(new URL(script, import.meta.url)), ...args],
    { stdio: 'inherit', env },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
