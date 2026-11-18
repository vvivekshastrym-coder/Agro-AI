/**
 * Agro AI — Schema.org Structured Data (JSON-LD) Generators
 * Validated against Google Rich Results specifications.
 */
import { BASE_CANONICAL_URL, DEFAULT_OG_IMAGE } from './config';

export function getOrganizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Agro AI',
    alternateName: 'Kishan AI',
    url: BASE_CANONICAL_URL,
    logo: `${BASE_CANONICAL_URL}/icons/icon-512x512.png`,
    description: 'Empowering Indian farmers with instant AI crop diagnosis, AGMARKNET mandi rates, and precision weather intelligence.',
    sameAs: [
      'https://twitter.com/AgroAI_Live',
      'https://github.com/vvivekshastrym-coder/Agro-AI',
    ],
    contactPoint: {
      '@type': 'ContactPoint',
      telephone: '+91-800-AGRO-AI',
      contactType: 'customer support',
      areaServed: 'IN',
      availableLanguage: ['en', 'kn', 'hi', 'te', 'ta'],
    },
  };
}

export function getWebsiteSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Agro AI',
    url: BASE_CANONICAL_URL,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${BASE_CANONICAL_URL}/mandi?crop={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };
}

export function getApplicationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: 'Agro AI Operating System',
    url: BASE_CANONICAL_URL,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web, Android, iOS',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'INR',
    },
    featureList: [
      'Instant Plant Disease Detection via Leaf Photo',
      'Live AGMARKNET APMC Mandi Market Prices',
      'Village-Level 7-Day Spray Window Forecast',
      'Government Scheme Eligibility & Application Links',
      'Multilingual AI Agronomist Chat',
    ],
  };
}

export interface BreadcrumbItem {
  name: string;
  path: string;
}

export function getBreadcrumbSchema(items: BreadcrumbItem[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.path.startsWith('http') ? item.path : `${BASE_CANONICAL_URL}${item.path}`,
    })),
  };
}

export interface ArticleSchemaProps {
  title: string;
  description: string;
  slug: string;
  publishedTime: string;
  modifiedTime?: string;
  authorName?: string;
  image?: string;
}

export function getArticleSchema(props: ArticleSchemaProps) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: props.title,
    description: props.description,
    image: props.image || DEFAULT_OG_IMAGE,
    datePublished: props.publishedTime,
    dateModified: props.modifiedTime || props.publishedTime,
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': `${BASE_CANONICAL_URL}/guides/${props.slug}`,
    },
    author: {
      '@type': 'Organization',
      name: props.authorName || 'Agro AI Agronomy Research Team',
      url: BASE_CANONICAL_URL,
    },
    publisher: {
      '@type': 'Organization',
      name: 'Agro AI',
      logo: {
        '@type': 'ImageObject',
        url: `${BASE_CANONICAL_URL}/icons/icon-512x512.png`,
      },
    },
  };
}

export interface FaqItem {
  question: string;
  answer: string;
}

export function getFaqSchema(faqs: FaqItem[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  };
}
