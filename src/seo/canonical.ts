/**
 * Agro AI — Dynamic Canonical URL Manager
 * Enforces canonical domain consistency and prevents duplicate content indexation.
 */
import { BASE_CANONICAL_URL } from './config';

// Query parameters that should never form part of a canonical indexing URL
const STRIP_QUERY_PARAMS = new Set([
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'fbclid',
  'gclid',
  'ref',
  'source',
  '_ga',
  'mc_cid',
  'mc_eid',
  'token',
  'session_id',
]);

/**
 * Normalizes a raw pathname or URL into a strict, canonical representation.
 * Rules:
 * 1. Protocol + Host is strictly https://www.agroai.live
 * 2. Trailing slashes are stripped (except for the root '/')
 * 3. Marketing/tracking query parameters are eliminated
 * 4. Path segments are converted to lowercase
 */
export function getCanonicalUrl(rawPathOrUrl: string, searchParams?: Record<string, string | string[] | undefined>): string {
  let pathname = rawPathOrUrl.trim();

  // If full URL was passed, extract pathname
  if (pathname.startsWith('http://') || pathname.startsWith('https://')) {
    try {
      const parsed = new URL(pathname);
      pathname = parsed.pathname;
    } catch {
      pathname = '/';
    }
  }

  // Ensure leading slash
  if (!pathname.startsWith('/')) {
    pathname = `/${pathname}`;
  }

  // Normalize path segments (lowercase, remove duplicate slashes)
  pathname = pathname.replace(/\/+/g, '/').toLowerCase();

  // Strip trailing slash unless it's the root '/'
  if (pathname.length > 1 && pathname.endsWith('/')) {
    pathname = pathname.slice(0, -1);
  }

  // Filter allowed query parameters if any (e.g. for canonical pagination ?page=2)
  const queryParts: string[] = [];
  if (searchParams) {
    const validKeys = Object.keys(searchParams)
      .filter((k) => !STRIP_QUERY_PARAMS.has(k.toLowerCase()))
      .sort();

    for (const key of validKeys) {
      const val = searchParams[key];
      if (typeof val === 'string' && val.length > 0) {
        queryParts.push(`${encodeURIComponent(key)}=${encodeURIComponent(val)}`);
      } else if (Array.isArray(val) && val.length > 0) {
        queryParts.push(`${encodeURIComponent(key)}=${encodeURIComponent(val[0])}`);
      }
    }
  }

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
  return `${BASE_CANONICAL_URL}${pathname}${queryString}`;
}

/**
 * Returns the Next.js Metadata `alternates` configuration with dynamic canonical.
 */
export function getCanonicalAlternates(path: string, searchParams?: Record<string, string | string[] | undefined>) {
  const canonical = getCanonicalUrl(path, searchParams);
  return {
    canonical,
    languages: {
      'en-IN': canonical,
      'kn-IN': `${canonical}?lang=kn`,
      'hi-IN': `${canonical}?lang=hi`,
      'x-default': canonical,
    },
  };
}
