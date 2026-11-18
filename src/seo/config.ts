/**
 * Agro AI — Production SEO & Metadata Configuration
 * Domain: https://www.agroai.live
 */

export interface PageSeoConfig {
  name: string;
  title: string;
  description: string;
  path: string;
  keywords: string[];
  changefreq: 'always' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'never';
  priority: number;
}

export const BASE_CANONICAL_URL = 'https://www.agroai.live';
export const DEFAULT_OG_IMAGE = `${BASE_CANONICAL_URL}/icons/icon-512x512.png`;

export const APP_SEO_PAGES: Record<string, PageSeoConfig> = {
  home: {
    name: 'Home',
    title: 'Agro AI: AI Crop Doctor, Live Mandi Rates & Farm Weather',
    description: 'Empowering Indian farmers with instant AI crop disease diagnosis, live APMC mandi prices, village weather forecasts, and multilingual farming advisory.',
    path: '/',
    keywords: [
      'Agro AI',
      'AI crop doctor',
      'plant disease diagnosis',
      'live mandi prices',
      'APMC market rates',
      'farm weather forecast',
      'PM-KISAN schemes',
      'Indian agriculture',
    ],
    changefreq: 'daily',
    priority: 1.0,
  },
  diagnose: {
    name: 'Crop Disease Diagnosis',
    title: 'AI Crop Doctor: Instant Plant Disease Diagnosis | Agro AI',
    description: 'Upload a leaf photo for instant crop disease detection, treatment remedies, and chemical spray dosage verified by ICAR agricultural guidelines.',
    path: '/diagnose',
    keywords: [
      'crop disease diagnosis',
      'plant doctor AI',
      'leaf disease detection',
      'crop pest control',
      'plant pathology India',
      'ICAR spray guide',
    ],
    changefreq: 'weekly',
    priority: 0.9,
  },
  agrogpt: {
    name: 'Agro GPT Assistant',
    title: 'AgroGPT: 24/7 AI Agronomist & Farming Assistant | Agro AI',
    description: 'Chat with your personal AI agronomist in your local language. Get instant expert advice on fertilizer schedules, pest control, and soil health.',
    path: '/agrogpt',
    keywords: [
      'AI agronomist',
      'AgroGPT',
      'kisan AI chat',
      'farming assistant in Kannada',
      'fertilizer calculation AI',
      'multilingual agriculture advisory',
    ],
    changefreq: 'weekly',
    priority: 0.9,
  },
  weather: {
    name: 'Weather Intelligence',
    title: 'Farm Weather Forecast & 7-Day Spray Window | Agro AI',
    description: 'Hyperlocal 7-day farm weather forecasts, live rainfall probability, and optimal pesticide spray advisory tailored to your village GPS coordinates.',
    path: '/weather',
    keywords: [
      'farm weather forecast',
      'pesticide spray window',
      'IMD agriculture weather',
      'village rain forecast',
      'crop weather advisory',
      'microclimate forecast',
    ],
    changefreq: 'daily',
    priority: 0.9,
  },
  mandi: {
    name: 'Mandi Market Prices',
    title: 'Live Mandi Prices & APMC Daily Market Rates | Agro AI',
    description: 'Track real-time APMC mandi prices across Karnataka & India. Compare wholesale modal, min, and max commodity rates directly from AGMARKNET.',
    path: '/mandi',
    keywords: [
      'mandi prices today',
      'APMC market rate',
      'AGMARKNET live prices',
      'Karnataka mandi rates',
      'vegetable wholesale price',
      'crop price comparison',
    ],
    changefreq: 'daily',
    priority: 0.9,
  },
  schemes: {
    name: 'Government Schemes & Land',
    title: 'Government Agriculture Schemes & PM-KISAN Portal | Agro AI',
    description: 'Explore Central & State farmer schemes, PM-KISAN status, KCC loans, FRUITS ID subsidies, and crop insurance eligibility with instant application links.',
    path: '/schemes',
    keywords: [
      'PM-KISAN status',
      'FRUITS Karnataka portal',
      'agriculture subsidies India',
      'Kisan Credit Card KCC',
      'crop insurance PMFBY',
      'Bhoomi RTC land survey',
    ],
    changefreq: 'daily',
    priority: 0.9,
  },
  plans: {
    name: 'Plans & Pricing',
    title: 'Agro AI Pricing: Free & Pro Plans for Farmers | Agro AI',
    description: 'Affordable AI farming plans for smallholders and commercial growers. Access unlimited crop diagnoses, live mandi alerts, and agronomist support.',
    path: '/plans',
    keywords: [
      'Agro AI subscription',
      'farming app pricing',
      'crop doctor plans',
      'farmer premium advisory',
      'smart farm membership',
    ],
    changefreq: 'weekly',
    priority: 0.8,
  },
  about: {
    name: 'About Agro AI',
    title: "About Agro AI: Building Bharat's Smart Farming OS",
    description: 'Learn how Agro AI empowers Indian farmers with AI crop diagnostics, AGMARKNET market intelligence, and multilingual agronomy support.',
    path: '/about',
    keywords: [
      'about Agro AI',
      'agritech India',
      'smart farming mission',
      'agricultural AI Bharat',
      'sustainable agriculture',
    ],
    changefreq: 'monthly',
    priority: 0.7,
  },
  contact: {
    name: 'Contact & Support',
    title: 'Contact Agro AI: Farmer Support & Agronomy Helpdesk',
    description: 'Get in touch with Agro AI agricultural experts and technical support. Reach us via WhatsApp, phone, or email for quick farming assistance.',
    path: '/contact',
    keywords: [
      'Agro AI contact',
      'farmer helpline',
      'kisan support',
      'agritech customer care',
      'agricultural grievance cell',
    ],
    changefreq: 'monthly',
    priority: 0.6,
  },
  guides: {
    name: 'Agricultural Guides',
    title: 'Crop Farming Guides & Package of Practices | Agro AI',
    description: 'Step-by-step agricultural guides for tomato, paddy, sugarcane, and cotton. Master seed treatment, drip irrigation, nutrient management, and yield maximization.',
    path: '/guides',
    keywords: [
      'crop farming guide',
      'package of practices',
      'tomato cultivation guide',
      'drip irrigation management',
      'organic crop protection',
      'ICAR crop guide',
    ],
    changefreq: 'weekly',
    priority: 0.8,
  },
  privacy: {
    name: 'Privacy Policy',
    title: 'Privacy Policy & Data Rights | Agro AI',
    description: 'Review the Agro AI privacy policy, zero session replay guarantee, DPDP Act 2023 compliance, and farmer data rights.',
    path: '/privacy',
    keywords: ['Agro AI privacy', 'farmer data rights', 'DPDP compliance India'],
    changefreq: 'monthly',
    priority: 0.5,
  },
  terms: {
    name: 'Terms of Service',
    title: 'Terms of Service & Farmer Protections | Agro AI',
    description: 'Read the terms of service governing Agro AI, including advisory disclaimers, membership terms, and user guidelines.',
    path: '/terms',
    keywords: ['Agro AI terms', 'farming service terms'],
    changefreq: 'monthly',
    priority: 0.5,
  },
};
