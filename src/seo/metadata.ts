import type { Metadata } from 'next';
import { APP_SEO_PAGES, BASE_CANONICAL_URL, DEFAULT_OG_IMAGE, type PageSeoConfig } from './config';

interface CustomMetadataOptions {
  title?: string;
  description?: string;
  path?: string;
  keywords?: string[];
  image?: string;
  noIndex?: boolean;
}

/**
 * Builds standard compliant Next.js Metadata for App Router
 */
export function constructMetadata(options: CustomMetadataOptions): Metadata {
  const title = options.title || APP_SEO_PAGES.home.title;
  const description = options.description || APP_SEO_PAGES.home.description;
  const path = options.path || '/';
  const canonicalUrl = `${BASE_CANONICAL_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const image = options.image || DEFAULT_OG_IMAGE;
  const noIndex = options.noIndex ?? false;

  return {
    title,
    description,
    keywords: [
      'Agro AI',
      'smart farming India',
      'AI crop doctor',
      'APMC mandi prices',
      ...(options.keywords || []),
    ],
    metadataBase: new URL(BASE_CANONICAL_URL),
    alternates: {
      canonical: canonicalUrl,
    },
    openGraph: {
      title,
      description,
      url: canonicalUrl,
      siteName: 'Agro AI',
      images: [
        {
          url: image,
          width: 1200,
          height: 630,
          alt: title,
        },
      ],
      locale: 'en_IN',
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [image],
      creator: '@AgroAI_Live',
    },
    robots: {
      index: !noIndex,
      follow: !noIndex,
      googleBot: {
        index: !noIndex,
        follow: !noIndex,
        'max-video-preview': -1,
        'max-image-preview': 'large',
        'max-snippet': -1,
      },
    },
  };
}

/**
 * Returns strongly-typed Next.js metadata for any registered page key.
 */
export function getMetadataForPage(pageKey: keyof typeof APP_SEO_PAGES, overrides?: Partial<PageSeoConfig>): Metadata {
  const page = APP_SEO_PAGES[pageKey] || APP_SEO_PAGES.home;
  return constructMetadata({
    title: overrides?.title || page.title,
    description: overrides?.description || page.description,
    path: overrides?.path || page.path,
    keywords: overrides?.keywords || page.keywords,
  });
}
