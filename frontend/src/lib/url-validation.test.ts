import { describe, expect, it } from 'vitest';

import { validateUrlInput } from './url-validation';

describe('validateUrlInput', () => {
  it.each([
    ['example.com', 'https://example.com/'],
    ['  example.com  ', 'https://example.com/'],
    ['https://example.com', 'https://example.com/'],
    ['http://example.com/path', 'http://example.com/path'],
    ['https://sub.example.co.uk/a?b=1', 'https://sub.example.co.uk/a?b=1'],
  ])('accepts %s', (input, normalized) => {
    const result = validateUrlInput(input);
    expect(result.valid).toBe(true);
    expect(result.normalized).toBe(normalized);
  });

  it.each([
    ['', 'Enter a website URL'],
    ['   ', 'Enter a website URL'],
    ['not a url', 'cannot contain spaces'],
    ['ftp://example.com', 'not supported'],
    ['javascript:alert(1)', 'not supported'],
    ['https://user:pw@example.com', 'credentials'],
    ['localhost', 'publicly reachable'],
    ['127.0.0.1', 'publicly reachable'],
    ['http://10.0.0.1/', 'private network'],
    ['http://192.168.1.1/', 'private network'],
    ['http://169.254.169.254/', 'private network'],
    ['http://100.64.0.1/', 'private network'],
    ['intranet', 'full domain name'],
  ])('rejects %s', (input, expectedMessage) => {
    const result = validateUrlInput(input);
    expect(result.valid).toBe(false);
    expect(result.message).toContain(expectedMessage);
  });

  it('does not claim to be a security control', () => {
    // Encoded forms that resolve to internal addresses are not caught here by design: only the
    // backend resolves DNS. This test documents that boundary so nobody later mistakes this
    // function for the guard.
    expect(validateUrlInput('http://2130706433/').valid).toBe(false); // no dot, caught incidentally
    expect(validateUrlInput('http://localtest.me/').valid).toBe(true); // resolves to 127.0.0.1
  });
});
