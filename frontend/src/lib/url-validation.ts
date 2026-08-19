/**
 * Client-side URL validation.
 *
 * This exists for immediate feedback in the input field, not for safety. The backend re-validates
 * authoritatively and is the only place that resolves DNS and enforces the address policy - a
 * check in the browser can always be bypassed, so treating it as a security control would be a
 * mistake.
 */

export interface UrlValidationResult {
  valid: boolean;
  normalized?: string;
  message?: string;
}

const OBVIOUSLY_LOCAL = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]']);
const PRIVATE_PATTERNS = [
  /^10\./,
  /^192\.168\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^169\.254\./,
  /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./,
];

export function validateUrlInput(raw: string): UrlValidationResult {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { valid: false, message: 'Enter a website URL to analyze.' };
  }
  if (/\s/.test(trimmed)) {
    return { valid: false, message: 'The URL cannot contain spaces.' };
  }

  // A scheme without `//` (mailto:, javascript:, data:) deserves a message about the scheme rather
  // than a generic parse failure. `example.com:8080` also matches this shape, so a numeric
  // remainder is treated as a port instead.
  const schemeOnly = /^([a-z][a-z0-9+.-]*):(?!\/\/)(.*)$/i.exec(trimmed);
  if (schemeOnly && !/^\d/.test(schemeOnly[2] ?? '')) {
    return {
      valid: false,
      message: `WebLens analyzes http:// and https:// pages. "${schemeOnly[1]}:" is not supported.`,
    };
  }

  const candidate = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return { valid: false, message: 'That does not look like a valid URL.' };
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return {
      valid: false,
      message: `WebLens analyzes http:// and https:// pages. "${parsed.protocol}" is not supported.`,
    };
  }
  if (parsed.username || parsed.password) {
    return { valid: false, message: 'Remove the credentials from the URL before scanning.' };
  }

  const host = parsed.hostname.toLowerCase();
  if (!host) {
    return { valid: false, message: 'The URL is missing a host name.' };
  }
  if (OBVIOUSLY_LOCAL.has(host) || host === '[::1]') {
    return { valid: false, message: 'WebLens analyzes publicly reachable sites, not local ones.' };
  }
  if (PRIVATE_PATTERNS.some((pattern) => pattern.test(host))) {
    return {
      valid: false,
      message: 'That address is on a private network. WebLens only analyzes public sites.',
    };
  }
  if (!host.includes('.')) {
    return {
      valid: false,
      message: 'Use a full domain name, for example example.com.',
    };
  }
  if (host.endsWith('.')) {
    parsed.hostname = host.slice(0, -1);
  }

  return { valid: true, normalized: parsed.toString() };
}
