import { heading, keyValueTable, section as join, table } from '../kit';
import {
  findingsBlock,
  limitationsBlock,
  scanErrorsBlock,
  sectionStatusBlock,
  standardDocument,
  unavailableBlock,
  type RenderContext,
} from '../shared';

/**
 * Architecture report, including the network section.
 *
 * Network observations are the evidence base for most architecture conclusions - protocol,
 * caching, CDN indicators, third-party surface - so they belong in the same document rather than a
 * ninth file the reader has to cross-reference.
 */
export function renderArchitecture(ctx: RenderContext): string {
  const networkSection = ctx.result.sections.network;
  const networkCtx: RenderContext = {
    ...ctx,
    sectionKey: 'network',
    section: networkSection,
  };

  const targetBlock = join(
    heading(2, 'Target and redirects'),
    keyValueTable([
      ['Scheme', ctx.result.target.scheme],
      ['Host', ctx.result.target.host],
      ['Port', ctx.result.target.port],
      ['Resolved addresses', ctx.result.target.resolved_ips.join(', ')],
      ['Redirect hops', ctx.result.target.redirect_chain.length],
      ['robots.txt verdict', describeRobots(ctx)],
    ]),
    ctx.result.target.redirect_chain.length > 0
      ? table(
          ['#', 'URL', 'Status', 'Location'],
          ctx.result.target.redirect_chain.map((hop, index) => [
            index + 1,
            hop.url,
            hop.status,
            hop.location,
          ]),
        )
      : '',
  );

  const networkBlock = join(
    heading(2, 'Network and external resources'),
    sectionStatusBlock(networkCtx),
    networkSection.meta.status === 'complete' || networkSection.meta.status === 'partial'
      ? join(findingsBlock(networkCtx), limitationsBlock(networkCtx))
      : unavailableBlock(networkCtx),
    scanErrorsBlock(ctx.result, 'network'),
  );

  return standardDocument(ctx, 'Architecture and runtime', targetBlock, networkBlock);
}

function describeRobots(ctx: RenderContext): string {
  const robots = ctx.result.target.robots;
  if (!robots) return 'not checked';
  if (robots.allowed === null || robots.allowed === undefined) {
    return `unknown (${robots.error ?? 'no verdict reached'})`;
  }
  const directive = robots.matched_directive ? ` via ${robots.matched_directive}` : '';
  return `${robots.allowed ? 'allowed' : 'disallowed'}${directive}`;
}
