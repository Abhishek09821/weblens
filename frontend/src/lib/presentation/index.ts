/**
 * Presentation layer.
 *
 * Transforms raw structured findings into human-readable views.
 * The scanner and analyzers remain untouched — this is a display concern only.
 */
export { buildOverview, type OverviewData } from './overview';
export { buildTechPresentation, type TechCategory, type TechItem } from './technology';
export { buildDesignPresentation, type DesignPresentation } from './design';
