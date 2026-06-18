import Link from 'next/link';
import { Zap, ArrowLeft } from 'lucide-react';

export const metadata = { title: 'Terms of Service — RankSpy' };

export default function TermsPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Terms of Service</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: June 18, 2026</p>

        <div className="prose prose-gray dark:prose-invert max-w-none space-y-8 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">1. Acceptance of Terms</h2>
            <p>By accessing or using RankSpy (&quot;the Service&quot;), operated at rankspy.app, you agree to be bound by these Terms of Service (&quot;Terms&quot;). If you do not agree to these Terms, do not use the Service.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">2. Description of Service</h2>
            <p>RankSpy is an App Store intelligence platform that provides keyword tracking, ranking analytics, competitor monitoring, and AI-powered insights for mobile app developers and marketers. The Service is provided on a subscription basis with various plan tiers.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">3. Account Registration</h2>
            <p className="mb-3">To use the Service, you must create an account. You agree to:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>Provide accurate and complete registration information</li>
              <li>Maintain the security of your password and account</li>
              <li>Promptly update your account information if it changes</li>
              <li>Accept responsibility for all activities under your account</li>
              <li>Notify us immediately of any unauthorized use of your account</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">4. Subscription Plans &amp; Billing</h2>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Free Trial:</strong> New accounts receive a 14-day free trial with access to premium features. No credit card is required to start the trial.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Paid Plans:</strong> After the trial, you may subscribe to a paid plan (Starter, Pro, or Enterprise). Paid subscriptions are billed monthly or annually, as selected at the time of purchase.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Automatic Renewal:</strong> Subscriptions automatically renew at the end of each billing period unless cancelled before the renewal date.</p>
            <p><strong className="text-gray-900 dark:text-white">Price Changes:</strong> We reserve the right to change pricing with 30 days&apos; notice. Price changes will take effect at your next billing cycle.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">5. Acceptable Use</h2>
            <p className="mb-3">You agree not to:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>Use the Service for any unlawful purpose or in violation of any applicable laws</li>
              <li>Attempt to gain unauthorized access to any part of the Service or its infrastructure</li>
              <li>Resell, redistribute, or sublicense access to the Service without written permission</li>
              <li>Use automated scripts or bots to scrape data from the platform beyond normal API usage</li>
              <li>Interfere with or disrupt the integrity or performance of the Service</li>
              <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
              <li>Use the Service to engage in competitive intelligence against RankSpy itself</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">6. Usage Limits</h2>
            <p>Each subscription plan has defined usage limits (app imports, keyword refreshes, AI requests, exports). If you exceed your plan limits, you will be prompted to upgrade. We reserve the right to throttle or suspend accounts that consistently exceed their plan limits.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">7. Intellectual Property</h2>
            <p className="mb-3">The Service, including its design, code, features, and content, is the property of RankSpy and is protected by intellectual property laws. You retain ownership of any data you upload or create on the platform.</p>
            <p>We grant you a limited, non-exclusive, non-transferable license to access and use the Service in accordance with these Terms for the duration of your subscription.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">8. Data &amp; Privacy</h2>
            <p>Your use of the Service is also governed by our <Link href="/privacy" className="text-indigo-600 dark:text-indigo-400 hover:underline">Privacy Policy</Link>. By using the Service, you consent to the collection and use of information as described in the Privacy Policy.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">9. Disclaimer of Warranties</h2>
            <p>The Service is provided &quot;as is&quot; and &quot;as available&quot; without warranties of any kind, either express or implied, including but not limited to implied warranties of merchantability, fitness for a particular purpose, and non-infringement. We do not guarantee that the Service will be uninterrupted, error-free, or secure.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">10. Limitation of Liability</h2>
            <p>To the maximum extent permitted by law, RankSpy and its officers, directors, employees, and agents shall not be liable for any indirect, incidental, special, consequential, or punitive damages, or any loss of profits, data, use, or goodwill, arising out of or related to your use of the Service.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">11. Cancellation &amp; Termination</h2>
            <p className="mb-3">You may cancel your subscription at any time from the Settings page. Upon cancellation, you will retain access until the end of your current billing period.</p>
            <p>We reserve the right to suspend or terminate your account if you violate these Terms, engage in fraudulent activity, or fail to pay subscription fees.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">12. Refunds</h2>
            <p>Please see our <Link href="/refund" className="text-indigo-600 dark:text-indigo-400 hover:underline">Refund Policy</Link> for details on eligibility and the refund process.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">13. Changes to Terms</h2>
            <p>We may update these Terms from time to time. We will notify you of any material changes by posting the updated Terms on this page and updating the &quot;Last updated&quot; date. Your continued use of the Service after changes constitutes acceptance of the new Terms.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">14. Governing Law</h2>
            <p>These Terms shall be governed by and construed in accordance with applicable laws. Any disputes arising from these Terms or your use of the Service shall be resolved through binding arbitration or in the courts of the applicable jurisdiction.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">15. Contact Us</h2>
            <p>If you have questions about these Terms, please contact us at <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
