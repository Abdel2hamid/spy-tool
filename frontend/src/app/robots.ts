import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/api/', '/payment/', '/verify-email/', '/admin/'],
      },
    ],
    sitemap: 'https://rankspy.app/sitemap.xml',
  };
}
