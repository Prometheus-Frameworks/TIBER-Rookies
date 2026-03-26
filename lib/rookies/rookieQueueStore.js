const STORAGE_KEY = 'tiber-rookie-queue-v1';
const PORTABILITY_VERSION = 1;

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function normalizeItem(item) {
  if (!item?.slug) return null;
  return {
    slug: String(item.slug),
    name: item.name ?? 'Unknown Rookie',
    position: item.position ?? 'N/A',
    school: item.school ?? 'School N/A',
    rookieGrade: Number.isFinite(item.rookieGrade) ? item.rookieGrade : null,
    classRank: Number.isFinite(item.classRank) ? item.classRank : null,
    tierLabel: item.tierLabel ?? 'Tier N/A',
    identityNote: item.identityNote ?? 'Profile note unavailable',
  };
}

function dedupeQueueBySlug(queue) {
  const seen = new Set();
  return queue.filter((item) => {
    if (seen.has(item.slug)) return false;
    seen.add(item.slug);
    return true;
  });
}

export function loadRookieQueue() {
  if (!canUseStorage()) return [];

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeItem).filter(Boolean);
  } catch {
    return [];
  }
}

function persistRookieQueue(queue) {
  if (!canUseStorage()) return;
  const normalized = queue.map(normalizeItem).filter(Boolean);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(dedupeQueueBySlug(normalized)));
}

export function addRookieToQueue(item) {
  const normalized = normalizeItem(item);
  if (!normalized) return loadRookieQueue();

  const queue = loadRookieQueue();
  if (queue.some((entry) => entry.slug === normalized.slug)) return queue;

  const next = [...queue, normalized];
  persistRookieQueue(next);
  return next;
}

export function removeRookieFromQueue(slug) {
  const queue = loadRookieQueue();
  const next = queue.filter((entry) => entry.slug !== slug);
  persistRookieQueue(next);
  return next;
}

export function isRookieQueued(slug) {
  return loadRookieQueue().some((entry) => entry.slug === slug);
}

export function moveQueuedRookie(slug, direction) {
  const queue = loadRookieQueue();
  const index = queue.findIndex((entry) => entry.slug === slug);
  if (index < 0) return queue;

  const target = direction === 'up' ? index - 1 : index + 1;
  if (target < 0 || target >= queue.length) return queue;

  const next = [...queue];
  const [moved] = next.splice(index, 1);
  next.splice(target, 0, moved);
  persistRookieQueue(next);
  return next;
}

export function clearRookieQueue() {
  persistRookieQueue([]);
  return [];
}

export function serializeRookieQueue() {
  const queue = loadRookieQueue();
  return {
    version: PORTABILITY_VERSION,
    exported_at: new Date().toISOString(),
    source: 'Prometheus-Frameworks/TIBER-Rookies rookie board queue',
    queue,
    metadata: {
      total_items: queue.length,
      storage_key: STORAGE_KEY,
      note: 'Browser-local portability artifact only. Not account/cloud sync.',
    },
  };
}

export function parseImportedRookieQueue(rawPayload) {
  let payload = rawPayload;
  if (typeof rawPayload === 'string') {
    try {
      payload = JSON.parse(rawPayload);
    } catch {
      throw new Error('Import failed: file is not valid JSON.');
    }
  }

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Import failed: expected a top-level JSON object.');
  }

  if (payload.version !== PORTABILITY_VERSION) {
    throw new Error(`Import failed: unsupported queue export version (${payload.version ?? 'missing'}).`);
  }

  if (!Array.isArray(payload.queue)) {
    throw new Error('Import failed: expected "queue" to be an array.');
  }

  const normalized = payload.queue.map((item, index) => {
    const next = normalizeItem(item);
    if (!next) {
      throw new Error(`Import failed: queue item ${index + 1} is missing a valid slug.`);
    }
    return next;
  });

  return {
    queue: dedupeQueueBySlug(normalized),
    metadata: payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {},
  };
}

export function replaceRookieQueue(queue) {
  persistRookieQueue(queue);
  return loadRookieQueue();
}

export function mergeImportedRookieQueue(importedQueue) {
  const existing = loadRookieQueue();
  const importedSlugs = new Set(importedQueue.map((item) => item.slug));
  const existingNotImported = existing.filter((item) => !importedSlugs.has(item.slug));
  const next = [...importedQueue, ...existingNotImported];
  persistRookieQueue(next);
  return loadRookieQueue();
}

export function importRookieQueue(rawPayload, options = {}) {
  const { mode = 'replace' } = options;
  const parsed = parseImportedRookieQueue(rawPayload);

  if (mode === 'replace') return replaceRookieQueue(parsed.queue);
  if (mode === 'merge') return mergeImportedRookieQueue(parsed.queue);

  throw new Error(`Import failed: unsupported import mode "${mode}".`);
}
