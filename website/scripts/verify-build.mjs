import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

const directory = fileURLToPath(new URL('../dist/client/', import.meta.url));
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '/Pefforza_4';
const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://tzii.github.io/Pefforza_4/';
const html = readFileSync(join(directory, 'index.html'), 'utf8');
let assetCount = 0;

function verifyAsset(url) {
  if (/^(?:data:|#)/.test(url)) return;
  const resolved = new URL(url, siteUrl);
  assert.equal(
    resolved.origin,
    new URL(siteUrl).origin,
    `Unexpected external asset: ${url}`,
  );
  assert.ok(
    resolved.pathname.startsWith(`${basePath}/`),
    `Asset is missing the Pages prefix: ${url}`,
  );
  const relative = decodeURIComponent(
    resolved.pathname.slice(basePath.length + 1),
  );
  assert.ok(
    existsSync(join(directory, relative)),
    `Missing exported asset: ${url}`,
  );
  assetCount++;
}

for (const match of html.matchAll(
  /<(?:script|link|img)\b[^>]*\b(?:src|href)="([^"]+)"/g,
)) {
  verifyAsset(match[1]);
}
assert.ok(assetCount > 5, 'Expected scripts, styles, and public image assets');
assert.ok(
  html.includes(`rel="canonical" href="${siteUrl}"`),
  'Missing public canonical URL',
);
assert.ok(
  html.indexOf('id="get-started"') < html.indexOf('id="play"'),
  'Project launch instructions should precede the demo',
);

const staticDirectory = join(directory, '_next', 'static');
const files = readdirSync(staticDirectory, { recursive: true });
for (const file of files.filter((name) => name.endsWith('.css'))) {
  const css = readFileSync(join(staticDirectory, file), 'utf8');
  for (const match of css.matchAll(/url\(["']?([^\s"')]+)["']?\)/g))
    verifyAsset(match[1]);
}
const worker = files.find((name) => /game\.worker-.*\.js$/.test(name));
assert.ok(worker, 'Expected the independent AI Web Worker');
const bundles = files
  .filter((name) => name.endsWith('.js') && name !== worker)
  .map((name) => readFileSync(join(staticDirectory, name), 'utf8'))
  .join('\n');
assert.ok(
  bundles.includes(`${siteUrl}_next/static/${worker.replaceAll('\\', '/')}`),
  'Worker URL must use the Pages prefix',
);

const responses = [];
const workerScope = { postMessage: (message) => responses.push(message) };
runInNewContext(readFileSync(join(staticDirectory, worker), 'utf8'), {
  self: workerScope,
});
const geometry = JSON.parse(
  readFileSync(new URL('../lib/geometry.json', import.meta.url), 'utf8'),
);
workerScope.onmessage({
  data: {
    board: Array(geometry.rows * geometry.cols).fill(geometry.empty),
    difficulty: 'hard',
  },
});
assert.equal(
  responses.length,
  1,
  'Compiled worker should answer a move request',
);
assert.equal(
  responses[0].column,
  Math.floor(geometry.cols / 2),
  'Hard should open in the center',
);
console.log(
  `Pages export verified: ${assetCount} asset references, canonical URL, section order, and compiled AI worker.`,
);
