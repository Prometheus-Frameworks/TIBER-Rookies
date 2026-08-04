import { renderRookieCard as renderBaseRookieCard } from './RookieCard.js';
import {
  CARD_RADAR_VIEWBOX,
  neutralAthleticPriorDisclosure,
  observedEvidenceReadiness,
} from '../../lib/rookies/phase1bPresentation.js';

function findPanelByTitle(container, title) {
  return [...container.querySelectorAll('.card-panel')].find(
    (panel) => panel.querySelector('.section-title')?.textContent?.trim() === title,
  ) ?? null;
}

function applyEvidenceReadiness(container, card) {
  const panel = findPanelByTitle(container, 'Position-aware Evidence');
  const meta = panel?.querySelector('.meta');
  if (!meta) return;
  const readiness = observedEvidenceReadiness(card);
  meta.textContent = readiness.label;
  meta.dataset.observedEvidenceAvailable = String(readiness.availableCount);
  meta.dataset.observedEvidenceTotal = String(readiness.totalCount);
}

function applyNeutralPriorDisclosure(container, card) {
  const disclosure = neutralAthleticPriorDisclosure(card);
  if (!disclosure) return;
  const panel = findPanelByTitle(container, 'Research Notes & Translation Signals');
  if (!panel) return;
  const existing = [...panel.querySelectorAll('.evidence-caveat')].find(
    (node) => node.textContent?.includes('Athletic testing data was not incorporated'),
  );
  if (existing) {
    existing.textContent = disclosure;
    return;
  }
  const note = document.createElement('div');
  note.className = 'meta evidence-caveat';
  note.textContent = disclosure;
  panel.append(note);
}

function applyRadarGeometry(container) {
  const radar = container.querySelector('.radar-chart');
  if (!radar) return;
  radar.setAttribute('viewBox', CARD_RADAR_VIEWBOX);
  radar.setAttribute('data-phase1b-label-padding', 'true');
  radar.style.overflow = 'visible';
  radar.querySelectorAll('text').forEach((label) => {
    label.setAttribute('dominant-baseline', 'middle');
  });
}

export function applyRookieCardPhase1B(container, card) {
  applyEvidenceReadiness(container, card);
  applyNeutralPriorDisclosure(container, card);
  applyRadarGeometry(container);
}

export function renderRookieCard(container, card) {
  renderBaseRookieCard(container, card, { afterRender: applyRookieCardPhase1B });
}
