import type { MetadataRoute } from 'next';
import { APP_SEO_PAGES, BASE_CANONICAL_URL } from './config';

/**
 * Next.js App Router dynamic sitemap.xml generator (app/sitemap.ts)
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const currentDate = new Date().toISOString();

  // Primary application static pages
  const staticRoutes: MetadataRoute.Sitemap = Object.values(APP_SEO_PAGES).map((page) => ({
    url: `${BASE_CANONICAL_URL}${page.path}`,
    lastModified: currentDate,
    changeFrequency: page.changefreq,
    priority: page.priority,
  }));

  // Dynamic agricultural guides
  const guideSlugs = [
    'crop-diseases',
    'crop-cultivation',
    'weather-advisories',
    'mandi-markets',
    'soil-and-fertilizers',
    'farmer-resources',
    'government-schemes',
  ];

  const guideRoutes: MetadataRoute.Sitemap = guideSlugs.map((slug) => ({
    url: `${BASE_CANONICAL_URL}/guides/${slug}`,
    lastModified: currentDate,
    changeFrequency: 'weekly',
    priority: 0.7,
  }));

  return [...staticRoutes, ...guideRoutes];
}
