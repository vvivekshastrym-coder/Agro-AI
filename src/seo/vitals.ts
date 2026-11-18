/**
 * Agro AI — Core Web Vitals Optimization Guidelines & Helpers
 * Target Metrics:
 * - LCP (Largest Contentful Paint) < 1.8s
 * - INP (Interaction to Next Paint) < 150ms
 * - CLS (Cumulative Layout Shift) < 0.05
 */

import type { NextWebVitalsMetric } from 'next/app';

/**
 * Custom Next.js Web Vitals reporter.
 * Emits real-user metrics (RUM) without third-party tracking overhead.
 */
export function reportWebVitals(metric: NextWebVitalsMetric) {
  const { id, name, label, value } = metric;

  // In development, log vitals to console with colored status
  if (process.env.NODE_ENV === 'development') {
    const isGood =
      (name === 'LCP' && value <= 2500) ||
      (name === 'INP' && value <= 200) ||
      (name === 'CLS' && value <= 0.1) ||
      (name === 'FCP' && value <= 1800) ||
      (name === 'TTFB' && value <= 800);

    const badge = isGood ? '🟢 PASS' : '🟠 NEEDS IMPROVEMENT';
    console.log(`[Web Vitals] ${name} (${label}): ${Math.round(value)}ms | ${badge} [${id}]`);
  }
}

/**
 * Image optimization rules for Next.js to ensure perfect LCP and CLS scores:
 * 1. For Hero / Above-the-fold images: Always set `priority={true}` to preload image.
 * 2. Always define explicit `width` and `height`, or use `fill` with a fixed-aspect-ratio parent container.
 * 3. Supply responsive `sizes` attribute so the browser only requests the exact device resolution.
 */
export const HERO_IMAGE_PROPS = {
  priority: true,
  loading: 'eager' as const,
  sizes: '(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw',
  placeholder: 'blur' as const,
};

export const SKELETON_CARD_STYLE = {
  minHeight: '280px',
  contain: 'paint layout' as const,
};
