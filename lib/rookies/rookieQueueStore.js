const STORAGE_KEY = 'tiber-rookie-queue-v1';
const PORTABILITY_VERSION = 2;
const NOTE_MAX_LENGTH = 160;
const QUEUE_TAG_OPTIONS = Object.freeze([
  'Target',
  'Fade',
  'Compare later',
  'Landing spot watch',
  'Contingency',
  'Tier break',
  'Upside swing',
  'Floor play',
]);

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function sanitizeQueueNote(note) {
  if (typeof note !== 'string') return '';
  return note
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, NOTE_MAX_LENGTH);
}

function sanitizeQueueTag(tag) {
  if (typeof tag !== 'string') return null;
  const trimmed = tag.trim();
  return QUEUE_TAG_OPTIONS.includes(trimmed) ? trimmed : null;
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
    queueNote: sanitizeQueueNote(item.queueNote),
    queueTag: sanitizeQueueTag(item.queueTag),
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

export function getRookieQueueTagOptions() {
  return [...QUEUE_TAG_OPTIONS];
}

export function getRookieQueueNoteMaxLength() {
  return NOTE_MAX_LENGTH;
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

function updateQueuedRookie(slug, updater) {
  const queue = loadRookieQueue();
  const next = queue.map((entry) => (entry.slug === slug ? normalizeItem(updater(entry)) : entry));
  persistRookieQueue(next);
  return loadRookieQueue();
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

export function updateQueuedRookieNote(slug, note) {
  return updateQueuedRookie(slug, (entry) => ({
    ...entry,
    queueNote: sanitizeQueueNote(note),
  }));
}

export function clearQueuedRookieNote(slug) {
  return updateQueuedRookieNote(slug, '');
}

export function updateQueuedRookieTag(slug, tag) {
  return updateQueuedRookie(slug, (entry) => ({
    ...entry,
    queueTag: sanitizeQueueTag(tag),
  }));
}

export function clearQueuedRookieTag(slug) {
  return updateQueuedRookieTag(slug, null);
}

export function getQueuedRookieAnnotation(slug) {
  const item = loadRookieQueue().find((entry) => entry.slug === slug);
  if (!item) return null;
  return {
    queueTag: item.queueTag,
    queueNote: item.queueNote,
  };
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
      annotation_fields: ['queueTag', 'queueNote'],
      queue_note_max_length: NOTE_MAX_LENGTH,
      queue_tag_options: [...QUEUE_TAG_OPTIONS],
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

  const version = Number(payload.version);
  if (version !== 1 && version !== PORTABILITY_VERSION) {
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
    version,
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
