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
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: June 19, 2026</p>

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
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Free Trial:</strong> New accounts receive a 7-day free trial with access to premium features. No credit card is required to start the trial.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Paid Plans:</strong> After the trial, you may subscribe to a paid plan (Starter, Pro, or Enterprise). Paid subscriptions are billed monthly or annually, as selected at the time of purchase.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Automatic Renewal:</strong> Subscriptions automatically renew at the end of each billing period unless cancelled before the renewal date. By subscribing, you authorize recurring charges to your payment method at the then-current rate. You may cancel at any time from your Settings page to prevent future renewals.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Payment Processing:</strong> All payments are securely processed by Stripe, Inc. By providing your payment details, you also agree to <a href="https://stripe.com/legal" className="text-indigo-600 dark:text-indigo-400 hover:underline" target="_blank" rel="noopener noreferrer">Stripe&apos;s Terms of Service</a>. We do not store your credit card details.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Billing Disputes:</strong> If you believe there is an error on your bill, contact us at <a href="mailto:billing@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">billing@rankspy.app</a> within 30 days of the charge. We encourage you to resolve billing issues directly with us before initiating a chargeback with your bank, as unresolved chargebacks may result in account suspension.</p>
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
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">14. Indemnification</h2>
            <p>You agree to indemnify, defend, and hold harmless RankSpy, its officers, directors, employees, and agents from any claims, damages, losses, liabilities, and expenses (including reasonable legal fees) arising out of your use of the Service, your violation of these Terms, or your infringement of any third-party rights.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">15. Governing Law &amp; Dispute Resolution</h2>
            <p className="mb-3">These Terms shall be governed by and construed in accordance with applicable laws. Any disputes arising from these Terms or your use of the Service shall be resolved as follows:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>You agree to first attempt to resolve any dispute informally by contacting us at <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a></li>
              <li>If a dispute cannot be resolved informally within 30 days, either party may pursue resolution through binding arbitration or in the courts of competent jurisdiction</li>
              <li>You agree to waive any right to participate in a class action lawsuit or class-wide arbitration</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">16. General Provisions</h2>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Severability:</strong> If any provision of these Terms is found to be unenforceable, the remaining provisions will continue in full force and effect.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Entire Agreement:</strong> These Terms, together with the Privacy Policy and Refund Policy, constitute the entire agreement between you and RankSpy regarding the Service.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Assignment:</strong> You may not assign or transfer your rights under these Terms without our prior written consent. We may assign our rights and obligations without restriction.</p>
            <p><strong className="text-gray-900 dark:text-white">Force Majeure:</strong> We shall not be liable for any failure or delay in performance due to circumstances beyond our reasonable control, including natural disasters, wars, pandemics, internet outages, or governmental actions.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">17. Contact Us</h2>
            <p>If you have questions about these Terms, please contact us at <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
