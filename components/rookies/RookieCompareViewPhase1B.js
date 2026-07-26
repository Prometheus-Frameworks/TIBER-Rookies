import {
  neutralAthleticPriorDisclosure,
  projectionTrackPercentages,
  sharedPprScaleMax,
} from '../../lib/rookies/phase1bPresentation.js';

function ensurePhase1BStyles() {
  if (document.querySelector('link[data-phase1b-mobile-integrity]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = '/components/rookies/phase1bMobileIntegrity.css';
  link.dataset.phase1bMobileIntegrity = 'true';
  document.head.append(link);
}

function findProjectionSection(container) {
  return [...container.querySelectorAll('.metrics')].find(
    (section) => section.querySelector('.section-title')?.textContent?.trim() === 'Year 1 PPR projection',
  ) ?? null;
}

function applySharedProjectionScale(container, leftCard, rightCard) {
  const section = findProjectionSection(container);
  if (!section) return;
  const projections = [leftCard?.pprProjection, rightCard?.pprProjection];
  const scaleMaximum = sharedPprScaleMax(...projections);
  if (scaleMaximum == null) return;

  let scaleNote = section.querySelector('.compare-ppr-shared-scale');
  if (!scaleNote) {
    scaleNote = document.createElement('div');
    scaleNote.className = 'meta compare-ppr-shared-scale';
    section.querySelector('.section-title')?.insertAdjacentElement('afterend', scaleNote);
  }
  scaleNote.textContent = `Shared track scale: 0–${scaleMaximum} PPR points.`;
  scaleNote.dataset.pprScaleMax = String(scaleMaximum);

  const panels = [...section.querySelectorAll('.compare-ppr-panel')];
  projections.forEach((projection, index) => {
    const percentages = projectionTrackPercentages(projection, scaleMaximum);
    if (!percentages) return;
    const track = panels[index]?.querySelector('.ppr-range-track');
    const fill = track?.querySelector('.ppr-range-fill');
    const marker = track?.querySelector('.ppr-range-median-marker');
    if (!track || !fill || !marker) return;
    fill.style.left = `${percentages.rangeLeft}%`;
    fill.style.width = `${percentages.rangeWidth}%`;
    marker.style.left = `${percentages.medianLeft}%`;
    track.dataset.pprScaleMax = String(scaleMaximum);
    track.setAttribute('aria-label', `Projection range on shared 0 to ${scaleMaximum} PPR point scale`);
  });
}

function applyNeutralPriorDisclosures(container, leftCard, rightCard) {
  const cards = [leftCard, rightCard];
  const panels = [...container.querySelectorAll('.compare-player-panel')];
  cards.forEach((card, index) => {
    const disclosure = neutralAthleticPriorDisclosure(card);
    if (!disclosure) return;
    const existing = [...(panels[index]?.querySelectorAll('.evidence-caveat') ?? [])].find(
      (node) => node.textContent?.includes('Athletic testing data was not incorporated'),
    );
    if (existing) existing.textContent = disclosure;
  });

  if (!cards.some((card) => card?.athleticSource === 'NEUTRAL_DEFAULT')) return;
  const radarCenter = container.querySelector('.compare-radar-center');
  const radarSvg = radarCenter?.querySelector('.compare-radar-svg');
  if (!radarCenter || !radarSvg) return;

  const firstAxisLabel = radarSvg.querySelector('text');
  if (firstAxisLabel) firstAxisLabel.textContent = 'ATH / prior';
  radarSvg.dataset.neutralPriorAxis = 'true';
  radarSvg.setAttribute(
    'aria-label',
    'Overlaid model-input radar; ATH prior denotes a neutral model input, not observed athletic testing',
  );

  if (!radarCenter.querySelector('.compare-radar-prior-note')) {
    const note = document.createElement('div');
    note.className = 'meta compare-radar-prior-note';
    note.textContent = 'ATH prior is a neutral model input, not observed athletic testing.';
    radarCenter.append(note);
  }
}

export function applyRookieComparePhase1B(container, leftCard, rightCard) {
  ensurePhase1BStyles();
  applySharedProjectionScale(container, leftCard, rightCard);
  applyNeutralPriorDisclosures(container, leftCard, rightCard);
}
