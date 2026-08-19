import type { ProblemDetail } from '@/types/analysis';

/** A structured error response from the API (RFC 9457 problem document). */
export class ApiProblemError extends Error {
  readonly problem: ProblemDetail;

  constructor(problem: ProblemDetail) {
    super(problem.detail ?? problem.title);
    this.name = 'ApiProblemError';
    this.problem = problem;
  }

  get code(): string {
    return this.problem.code;
  }

  get retryable(): boolean {
    return this.problem.retryable;
  }
}

/**
 * The response arrived but did not match the contract.
 *
 * Kept distinct from a transport failure: this means the backend and frontend disagree about the
 * payload shape, which is a deployment/version problem the user needs told about plainly rather
 * than a blank screen or a crash deep inside a component.
 */
export class ContractError extends Error {
  readonly issues: string[];

  constructor(message: string, issues: string[]) {
    super(message);
    this.name = 'ContractError';
    this.issues = issues;
  }
}

/** The request never completed: backend down, network gone, request aborted. */
export class TransportError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'TransportError';
  }
}

export function describeError(error: unknown): { title: string; detail: string; code?: string } {
  if (error instanceof ApiProblemError) {
    return {
      title: error.problem.title,
      detail: error.problem.detail ?? '',
      code: error.problem.code,
    };
  }
  if (error instanceof ContractError) {
    return {
      title: 'Unexpected response shape',
      detail: `${error.message} ${error.issues.slice(0, 3).join('; ')}`.trim(),
      code: 'CONTRACT_MISMATCH',
    };
  }
  if (error instanceof TransportError) {
    return {
      title: 'Could not reach the WebLens backend',
      detail: `${error.message} Check that the API is running on http://127.0.0.1:8000.`,
      code: 'TRANSPORT',
    };
  }
  return {
    title: 'Something went wrong',
    detail: error instanceof Error ? error.message : String(error),
  };
}
