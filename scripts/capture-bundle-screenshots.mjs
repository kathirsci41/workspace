import playwright from '../frontend/node_modules/playwright/index.js';
import fs from 'node:fs/promises';
import path from 'node:path';

const { chromium } = playwright;
const args = parseArgs(process.argv.slice(2));
const baseUrl = (args['base-url'] || 'http://127.0.0.1:5180').replace(/\/$/, '');
const apiBase = (args['api-base'] || 'http://127.0.0.1:8100/api').replace(/\/$/, '');
const bundleId = args['bundle-id'];
const bundleName = args['bundle-name'];
const outDir = args['out-dir'];

if (!outDir) {
  throw new Error('--out-dir is required.');
}

await fs.mkdir(outDir, { recursive: true });

const resolvedBundleId = bundleId || await findBundleId(bundleName);
if (!resolvedBundleId) {
  throw new Error('Provide --bundle-id or a --bundle-name that exists in the API.');
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });

const routes = [
  ['01-bundles.png', '/bundles'],
  ['02-overview.png', `/bundles/${resolvedBundleId}/overview`],
  ['03-documents.png', `/bundles/${resolvedBundleId}/documents`],
  ['04-extraction-review.png', `/bundles/${resolvedBundleId}/extraction`],
  ['05-review-results.png', `/bundles/${resolvedBundleId}/verification`],
  ['06-open-issues.png', `/bundles/${resolvedBundleId}/issues`],
  ['07-manual-correction-history.png', `/bundles/${resolvedBundleId}/audit`],
  ['08-exports.png', `/bundles/${resolvedBundleId}/exports`],
];

for (const [filename, route] of routes) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(outDir, filename), fullPage: true });
}

await browser.close();
console.log(JSON.stringify({ baseUrl, apiBase, bundleId: resolvedBundleId, outDir }, null, 2));

async function findBundleId(name) {
  if (!name) {
    return null;
  }
  const response = await fetch(`${apiBase}/bundles`);
  if (!response.ok) {
    throw new Error(`GET /bundles failed ${response.status}`);
  }
  const bundles = await response.json();
  const match = bundles.find((bundle) => bundle.bundle_number === name);
  return match?.id || null;
}

function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 1) {
    const token = values[index];
    if (!token.startsWith('--')) {
      continue;
    }
    const key = token.slice(2);
    const next = values[index + 1];
    if (!next || next.startsWith('--')) {
      parsed[key] = 'true';
      continue;
    }
    parsed[key] = next;
    index += 1;
  }
  return parsed;
}
