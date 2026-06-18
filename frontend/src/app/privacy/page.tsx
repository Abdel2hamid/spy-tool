import Link from 'next/link';
import { Zap, ArrowLeft } from 'lucide-react';

export const metadata = { title: 'Privacy Policy — RankSpy' };

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <header className="border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex items-center gap-4">
          <Link href="/landing" className="flex items-center gap-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <Link href="/landing" className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Privacy Policy</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: June 18, 2026</p>

        <div className="prose prose-gray dark:prose-invert max-w-none space-y-8 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">1. Introduction</h2>
            <p>RankSpy (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) operates the website rankspy.app and the RankSpy platform. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our service.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">2. Information We Collect</h2>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Account Information:</strong> When you register, we collect your email address, name (optional), and encrypted password.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Usage Data:</strong> We automatically collect information about how you interact with the platform, including pages visited, features used, app imports, keyword searches, and AI requests.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Device Information:</strong> We collect browser type, operating system, IP address, and device identifiers for security and analytics purposes.</p>
            <p><strong className="text-gray-900 dark:text-white">Payment Information:</strong> If you subscribe to a paid plan, payment processing is handled by our third-party payment processor. We do not store credit card numbers on our servers.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">3. How We Use Your Information</h2>
            <ul className="list-disc pl-5 space-y-2">
              <li>To provide, maintain, and improve the RankSpy platform</li>
              <li>To process your transactions and manage your subscription</li>
              <li>To send you service-related communications and updates</li>
              <li>To monitor usage patterns and enforce plan limits</li>
              <li>To detect and prevent fraud, abuse, and security incidents</li>
              <li>To comply with legal obligations</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">4. Data Sharing</h2>
            <p>We do not sell your personal information. We may share data with:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li><strong className="text-gray-900 dark:text-white">Service Providers:</strong> Third-party vendors who assist with hosting, analytics, payment processing, and email delivery</li>
              <li><strong className="text-gray-900 dark:text-white">Legal Requirements:</strong> When required by law, court order, or governmental authority</li>
              <li><strong className="text-gray-900 dark:text-white">Business Transfers:</strong> In connection with a merger, acquisition, or sale of assets</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">5. Data Retention</h2>
            <p>We retain your account data for as long as your account is active. If you delete your account, we will remove your personal data within 30 days, except where retention is required by law.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">6. Data Security</h2>
            <p>We implement industry-standard security measures including encryption in transit (TLS), encrypted password storage (bcrypt), and secure infrastructure hosting. However, no method of transmission over the Internet is 100% secure.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">7. Your Rights</h2>
            <p>Depending on your jurisdiction, you may have the right to:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li>Access your personal data</li>
              <li>Correct inaccurate data</li>
              <li>Delete your account and associated data</li>
              <li>Export your data in a portable format</li>
              <li>Opt out of marketing communications</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">8. Cookies</h2>
            <p>We use essential cookies for authentication and session management. We do not use third-party advertising cookies. See our <Link href="/cookies" className="text-indigo-600 dark:text-indigo-400 hover:underline">Cookie Policy</Link> for more details.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">9. Changes to This Policy</h2>
            <p>We may update this Privacy Policy from time to time. We will notify you of any material changes by posting the new policy on this page and updating the &quot;Last updated&quot; date.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">10. Contact Us</h2>
            <p>If you have questions about this Privacy Policy, please contact us at <a href="mailto:privacy@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">privacy@rankspy.app</a>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
