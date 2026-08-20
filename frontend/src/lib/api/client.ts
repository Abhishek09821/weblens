/**
 * Typed API client.
 *
 * Every response passes through a zod schema before it reaches the app, so a contract mismatch
 * surfaces as a clear message at the boundary instead of `undefined` deep inside a component.
 */
import {
  analysisResultSchema,
  capabilitiesSchema,
  healthSchema,
  problemDetailSchema,
  scanAcceptedSchema,
  scanJobStateSchema,
  type AnalysisResult,
  type Capabilities,
  type Health,
  type ScanAccepted,
  type ScanJobState,
  type SectionKey,
} from '@/types/analysis';
import type { z } from 'zod';

import { ApiProblemError, ContractError, TransportError } from './errors';

/** Same-origin by default: the Vite dev server proxies `/api` and `/health` to the backend. */
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const API_V1 = `${API_BASE}/api/v1`;

export interface ScanRequestOptions {
  include_screenshot?: boolean;
  include_full_page_screenshot?: boolean;
  sections?: SectionKey[] | null;
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit & { expectedStatus?: number[] },
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new TransportError('The request could not be sent.', { cause });
  }

  if (!response.ok) {
    throw await toProblem(response);
  }

  const payload: unknown = await response.json().catch((cause: unknown) => {
    throw new ContractError('The response was not valid JSON.', [String(cause)]);
  });

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ContractError(
      'The response did not match the expected schema.',
      parsed.error.issues.map((issue) => `${issue.path.join('.') || 'root'}: ${issue.message}`),
    );
  }
  return parsed.data;
}

async function toProblem(response: Response): Promise<Error> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return new TransportError(`The server responded ${response.status} without a body.`);
  }
  const problem = problemDetailSchema.safeParse(body);
  if (problem.success) return new ApiProblemError(problem.data);
  return new ContractError(`The server responded ${response.status} in an unexpected format.`, []);
}

export const api = {
  async health(signal?: AbortSignal): Promise<Health> {
    return request(`${API_BASE}/health`, healthSchema, { signal });
  },

  async capabilities(signal?: AbortSignal): Promise<Capabilities> {
    return request(`${API_V1}/capabilities`, capabilitiesSchema, { signal });
  },

  async createScan(url: string, options?: ScanRequestOptions): Promise<ScanAccepted> {
    return request(`${API_V1}/scans`, scanAcceptedSchema, {
      method: 'POST',
      body: JSON.stringify(options ? { url, options } : { url }),
    });
  },

  async jobState(scanId: string, signal?: AbortSignal): Promise<ScanJobState> {
    return request(`${API_V1}/scans/${scanId}`, scanJobStateSchema, { signal });
  },

  async result(scanId: string, signal?: AbortSignal): Promise<AnalysisResult> {
    return request(`${API_V1}/scans/${scanId}/result`, analysisResultSchema, { signal });
  },

  /**
   * Release the server-side copy once the result is stored locally.
   *
   * Failure is deliberately swallowed: the client already has the data, and the buffer expires on
   * its own. Surfacing this would be alarming noise about something already handled.
   */
  async deleteScan(scanId: string): Promise<void> {
    try {
      await fetch(`${API_V1}/scans/${scanId}`, { method: 'DELETE' });
    } catch {
      // Intentionally ignored; see above.
    }
  },

  eventsUrl(scanId: string): string {
    return `${API_V1}/scans/${scanId}/events`;
  },

  /** Generate an AI summary of the analysis (optional, requires GROQ_API_KEY on backend). */
  async summarize(result: unknown): Promise<{ available: boolean; summary: string | null; model: string | null; disclaimer: string }> {
    try {
      const response = await fetch(`${API_V1}/ai/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result_data: result }),
      });
      if (!response.ok) return { available: false, summary: null, model: null, disclaimer: '' };
      return await response.json();
    } catch {
      return { available: false, summary: null, model: null, disclaimer: '' };
    }
  },
};
