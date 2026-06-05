// Test-only ESM resolve hook.
//
// A few browser modules (e.g. lib/rookies/compareRookies.js) import siblings
// with browser-absolute specifiers like '/lib/rookies/selectRookieEvidenceMetrics.js'.
// The static server serves the repo root, so '/lib/...' resolves correctly in
// the browser. Node's resolver instead reads '/lib/...' from the filesystem
// root and fails. This hook rewrites '/lib', '/components' and '/cards'
// specifiers to repo-root file URLs so the same source loads unmodified in
// Node tests. Source files keep their deliberate absolute-import style.

import { pathToFileURL } from 'node:url';
import path from 'node:path';

const REPO_ROOT = path.resolve(import.meta.dirname, '..', '..');
const BROWSER_ROOTS = ['/lib/', '/components/', '/cards/'];

export async function resolve(specifier, context, nextResolve) {
  if (BROWSER_ROOTS.some((root) => specifier.startsWith(root))) {
    const target = pathToFileURL(path.join(REPO_ROOT, specifier)).href;
    return nextResolve(target, context);
  }
  return nextResolve(specifier, context);
}
