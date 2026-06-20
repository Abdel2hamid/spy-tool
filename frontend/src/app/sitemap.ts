import type { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const base = 'https://rankspy.app';
  const now = new Date().toISOString();

  return [
    { url: base, lastModified: now, changeFrequency: 'daily', priority: 1.0 },
    { url: `${base}/landing`, lastModified: now, changeFrequency: 'weekly', priority: 0.9 },
    { url: `${base}/about`, lastModified: now, changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/contact`, lastModified: now, changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/data-sources`, lastModified: now, changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/support`, lastModified: now, changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/privacy`, lastModified: now, changeFrequency: 'monthly', priority: 0.4 },
    { url: `${base}/terms`, lastModified: now, changeFrequency: 'monthly', priority: 0.4 },
    { url: `${base}/cookies`, lastModified: now, changeFrequency: 'monthly', priority: 0.3 },
    { url: `${base}/refund`, lastModified: now, changeFrequency: 'monthly', priority: 0.3 },
    { url: `${base}/login`, lastModified: now, changeFrequency: 'monthly', priority: 0.5 },
    { url: `${base}/signup`, lastModified: now, changeFrequency: 'monthly', priority: 0.5 },
  ];
}
