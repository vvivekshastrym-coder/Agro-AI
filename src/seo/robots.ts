import type { MetadataRoute } from 'next';
import { BASE_CANONICAL_URL } from './config';

/**
 * Next.js App Router dynamic robots.txt generator (app/robots.ts)
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: [
          '/',
          '/diagnose',
          '/agrogpt',
          '/weather',
          '/mandi',
          '/schemes',
          '/my-land',
          '/plans',
          '/about',
          '/contact',
          '/guides',
          '/guides/*',
          '/privacy',
          '/terms',
          '/cookies',
          '/css/*',
          '/js/*',
          '/fonts/*',
          '/icons/*',
        ],
        disallow: [
          '/admin',
          '/admin/*',
          '/admin-console',
          '/api/*',
          '/delete-account',
          '/docs',
          '/redoc',
          '/scratch/*',
          '/releases/*',
        ],
      },
      {
        userAgent: 'Googlebot',
        allow: '/',
      },
      {
        userAgent: 'Googlebot-Image',
        allow: ['/icons/*', '/favicon.ico', '/favicon.png'],
      },
      {
        userAgent: 'Bingbot',
        allow: '/',
      },
      {
        userAgent: 'Applebot',
        allow: '/',
      },
    ],
    sitemap: `${BASE_CANONICAL_URL}/sitemap.xml`,
    host: BASE_CANONICAL_URL,
  };
}
