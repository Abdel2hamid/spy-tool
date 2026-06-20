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
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: June 19, 2026</p>

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
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">4. Data Sharing &amp; Third-Party Services</h2>
            <p>We do not sell your personal information. We may share data with:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li><strong className="text-gray-900 dark:text-white">Stripe (Payment Processing):</strong> We use Stripe, Inc. to process payments. When you subscribe, Stripe collects your payment card details, billing address, and transaction data directly. Stripe&apos;s use of your data is governed by <a href="https://stripe.com/privacy" className="text-indigo-600 dark:text-indigo-400 hover:underline" target="_blank" rel="noopener noreferrer">Stripe&apos;s Privacy Policy</a>. We do not store credit card numbers on our servers.</li>
              <li><strong className="text-gray-900 dark:text-white">Resend (Email Delivery):</strong> We use Resend to send transactional emails (verification, password reset). Resend processes your email address for delivery purposes only.</li>
              <li><strong className="text-gray-900 dark:text-white">Infrastructure Providers:</strong> We use cloud hosting services to store and process data. These providers maintain industry-standard security certifications.</li>
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
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">7. Your Rights (GDPR &amp; CCPA)</h2>
            <p className="mb-3">Depending on your jurisdiction, you may have the right to:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong className="text-gray-900 dark:text-white">Access:</strong> Request a copy of the personal data we hold about you</li>
              <li><strong className="text-gray-900 dark:text-white">Rectification:</strong> Correct inaccurate or incomplete data</li>
              <li><strong className="text-gray-900 dark:text-white">Erasure:</strong> Request deletion of your account and associated data</li>
              <li><strong className="text-gray-900 dark:text-white">Data Portability:</strong> Export your data in a machine-readable format</li>
              <li><strong className="text-gray-900 dark:text-white">Restriction:</strong> Request that we restrict processing of your data</li>
              <li><strong className="text-gray-900 dark:text-white">Objection:</strong> Object to processing based on legitimate interests</li>
              <li><strong className="text-gray-900 dark:text-white">Opt Out:</strong> Opt out of marketing communications at any time</li>
            </ul>
            <p className="mt-3"><strong className="text-gray-900 dark:text-white">How to exercise your rights:</strong> Send your request to <a href="mailto:privacy@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">privacy@rankspy.app</a>. We will respond within 30 days. We may ask you to verify your identity before processing your request.</p>
            <p className="mt-3"><strong className="text-gray-900 dark:text-white">California Residents (CCPA/CPRA):</strong> You have the right to know what personal information we collect, request its deletion, and opt out of its sale (we do not sell personal information). You will not be discriminated against for exercising these rights.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">8. International Data Transfers</h2>
            <p>Your data may be processed on servers located outside your country of residence. We ensure that any cross-border data transfers comply with applicable data protection laws through appropriate safeguards, including standard contractual clauses where required.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">9. Children&apos;s Privacy</h2>
            <p>RankSpy is not intended for use by anyone under the age of 16. We do not knowingly collect personal information from children. If we learn that we have collected data from a child under 16, we will promptly delete it. If you believe a child has provided us with personal information, please contact us at <a href="mailto:privacy@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">privacy@rankspy.app</a>.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">10. Cookies</h2>
            <p>We use essential cookies for authentication and session management. We do not use third-party advertising cookies. See our <Link href="/cookies" className="text-indigo-600 dark:text-indigo-400 hover:underline">Cookie Policy</Link> for more details.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">11. Changes to This Policy</h2>
            <p>We may update this Privacy Policy from time to time. We will notify you of any material changes by posting the new policy on this page and updating the &quot;Last updated&quot; date.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">12. Contact Us</h2>
            <p>If you have questions about this Privacy Policy, please contact us at <a href="mailto:privacy@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">privacy@rankspy.app</a>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
