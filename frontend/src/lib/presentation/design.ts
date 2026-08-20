/**
 * Design presentation model.
 *
 * Transforms raw style measurements into human-readable design analysis.
 * Color values become swatches. Font lists become typography systems.
 * Layout measurements become design pattern descriptions.
 */
import type { AnalysisResult, Finding } from '@/types/analysis';

export interface DesignPresentation {
  summary: string;
  colors: ColorSystem;
  typography: TypographySystem;
  layout: LayoutSystem;
  motion: MotionSystem;
  media: MediaSystem;
}

export interface ColorSystem {
  backgrounds: ColorEntry[];
  texts: ColorEntry[];
  available: boolean;
}

export interface ColorEntry {
  value: string;
  hex: string | null;
  count?: number;
}

export interface TypographySystem {
  loadedFonts: string[];
  fontFamilies: string[];
  weights: string[];
  sizes: string[];
  lineHeights: string[];
  available: boolean;
}

export interface LayoutSystem {
  displayTypes: string[];
  borderRadii: string[];
  shadows: string[];
  gaps: string[];
  breakpoints: string[];
  hasResponsive: boolean;
  hasOverflow: boolean;
  overflowWidths: string[];
  available: boolean;
}

export interface MotionSystem {
  transitions: string[];
  animations: string[];
  keyframeCount: number | null;
  available: boolean;
}

export interface MediaSystem {
  imageCount: number | null;
  lazyLoaded: number | null;
  svgCount: number | null;
  videoCount: number | null;
  pictureCount: number | null;
  formats: string[];
  available: boolean;
}

export function buildDesignPresentation(result: AnalysisResult): DesignPresentation {
  const section = result.sections.design;
  const findings = section.findings;

  const colors = extractColors(findings);
  const typography = extractTypography(findings);
  const layout = extractLayout(findings);
  const motion = extractMotion(findings);
  const media = extractMedia(result);

  const summary = buildDesignSummary(colors, typography, layout, motion, media);

  return { summary, colors, typography, layout, motion, media };
}

function extractColors(findings: Finding[]): ColorSystem {
  const bgFinding = findings.find((f) => f.id === 'design.color:background-colors');
  const textFinding = findings.find((f) => f.id === 'design.color:text-colors');

  const backgrounds = (bgFinding?.values ?? []).slice(0, 12).map(parseColor);
  const texts = (textFinding?.values ?? []).slice(0, 12).map(parseColor);

  return {
    backgrounds,
    texts,
    available: backgrounds.length > 0 || texts.length > 0,
  };
}

function extractTypography(findings: Finding[]): TypographySystem {
  const fonts = findings.find((f) => f.id === 'design.typography:loaded-fonts');
  const families = findings.find((f) => f.id === 'design.typography:font-families');
  const weights = findings.find((f) => f.id === 'design.typography:font-weights');
  const sizes = findings.find((f) => f.id === 'design.typography:font-sizes');
  const lineHeights = findings.find((f) => f.id === 'design.typography:line-heights');

  return {
    loadedFonts: dedup(fonts?.values ?? []),
    fontFamilies: (families?.values ?? []).slice(0, 8),
    weights: (weights?.values ?? []).slice(0, 8),
    sizes: (sizes?.values ?? []).slice(0, 12),
    lineHeights: (lineHeights?.values ?? []).slice(0, 6),
    available: (fonts?.values?.length ?? 0) > 0 || (families?.values?.length ?? 0) > 0,
  };
}

function extractLayout(findings: Finding[]): LayoutSystem {
  const display = findings.find((f) => f.id === 'design.layout:display-types');
  const radii = findings.find((f) => f.id === 'design.layout:border-radius');
  const shadows = findings.find((f) => f.id === 'design.layout:box-shadows');
  const gaps = findings.find((f) => f.id === 'design.layout:gap-values');
  const breakpoints = findings.find((f) => f.id === 'design.layout:breakpoints');
  const overflow = findings.find((f) => f.id === 'design.layout:horizontal-overflow');

  return {
    displayTypes: (display?.values ?? []).slice(0, 10),
    borderRadii: (radii?.values ?? []).slice(0, 8),
    shadows: (shadows?.values ?? []).slice(0, 5),
    gaps: (gaps?.values ?? []).slice(0, 8),
    breakpoints: (breakpoints?.values ?? []).slice(0, 10),
    hasResponsive: (breakpoints?.values?.length ?? 0) > 0,
    hasOverflow: overflow != null,
    overflowWidths: (overflow?.values ?? []),
    available: (display?.values?.length ?? 0) > 0,
  };
}

function extractMotion(findings: Finding[]): MotionSystem {
  const transitions = findings.find((f) => f.id === 'design.motion:transitions');
  const animations = findings.find((f) => f.id === 'design.motion:animations');
  const keyframes = findings.find((f) => f.id === 'design.motion:keyframes');

  return {
    transitions: (transitions?.values ?? []).slice(0, 6),
    animations: (animations?.values ?? []).slice(0, 6),
    keyframeCount: typeof keyframes?.value === 'number' ? keyframes.value : null,
    available: (transitions?.values?.length ?? 0) > 0 || (animations?.values?.length ?? 0) > 0,
  };
}

function extractMedia(result: AnalysisResult): MediaSystem {
  const findings = result.sections.design.findings;
  const imgFinding = findings.find((f) => f.id === 'design.media:image-count');
  const svgFinding = findings.find((f) => f.id === 'design.media:svg-usage');
  const videoFinding = findings.find((f) => f.id === 'design.media:video-usage');
  const pictureFinding = findings.find((f) => f.id === 'design.media:picture-usage');
  const formatFinding = findings.find((f) => f.id === 'design.media:image-formats');

  return {
    imageCount: typeof imgFinding?.value === 'number' ? imgFinding.value : null,
    lazyLoaded: imgFinding?.details?.lazy_loaded as number | null ?? null,
    svgCount: typeof svgFinding?.value === 'number' ? svgFinding.value : null,
    videoCount: typeof videoFinding?.value === 'number' ? videoFinding.value : null,
    pictureCount: typeof pictureFinding?.value === 'number' ? pictureFinding.value : null,
    formats: (formatFinding?.values ?? []).slice(0, 8),
    available: imgFinding != null || svgFinding != null,
  };
}

function buildDesignSummary(
  colors: ColorSystem,
  typography: TypographySystem,
  layout: LayoutSystem,
  motion: MotionSystem,
  _media: MediaSystem,
): string {
  const parts: string[] = [];

  if (typography.loadedFonts.length > 0) {
    parts.push(`${typography.loadedFonts.slice(0, 2).join(' and ')} typography`);
  }
  if (layout.displayTypes.includes('flex') || layout.displayTypes.includes('grid')) {
    parts.push('modern CSS layout');
  }
  if (layout.hasResponsive) parts.push('responsive design');
  if (layout.borderRadii.length > 0) parts.push('rounded elements');
  if (layout.shadows.length > 0) parts.push('subtle shadows');
  if (motion.available) parts.push('CSS transitions/animations');
  if (colors.available && colors.backgrounds.length > 3) parts.push('defined color system');

  if (parts.length === 0) return 'Design details could not be fully observed for this page.';
  return `The page uses ${parts.join(', ')}.`;
}

function parseColor(raw: string): ColorEntry {
  const hex = rgbToHex(raw);
  return { value: raw, hex };
}

function rgbToHex(color: string): string | null {
  const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!match) return color.startsWith('#') ? color : null;
  const r = parseInt(match[1], 10);
  const g = parseInt(match[2], 10);
  const b = parseInt(match[3], 10);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

function dedup(arr: string[]): string[] {
  return [...new Set(arr)];
}
