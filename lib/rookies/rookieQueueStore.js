const STORAGE_KEY = 'tiber-rookie-queue-v1';

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

export function persistRookieQueue(queue) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(queue.map(normalizeItem).filter(Boolean)));
}

function notify(queue) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('rookie-queue-updated', { detail: queue }));
}

export function addRookieToQueue(item) {
  const normalized = normalizeItem(item);
  if (!normalized) return loadRookieQueue();

  const queue = loadRookieQueue();
  if (queue.some((entry) => entry.slug === normalized.slug)) return queue;

  const next = [...queue, normalized];
  persistRookieQueue(next);
  notify(next);
  return next;
}

export function removeRookieFromQueue(slug) {
  const queue = loadRookieQueue();
  const next = queue.filter((entry) => entry.slug !== slug);
  persistRookieQueue(next);
  notify(next);
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
  notify(next);
  return next;
}

export function clearRookieQueue() {
  persistRookieQueue([]);
  notify([]);
  return [];
}
