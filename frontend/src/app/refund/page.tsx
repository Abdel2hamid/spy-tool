import Link from 'next/link';
import { Zap, ArrowLeft } from 'lucide-react';

export const metadata = { title: 'Refund Policy — RankSpy' };

export default function RefundPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Refund Policy</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: June 18, 2026</p>

        <div className="prose prose-gray dark:prose-invert max-w-none space-y-8 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">1. Overview</h2>
            <p>We want you to be completely satisfied with RankSpy. If the platform does not meet your expectations, we offer refunds under the conditions described below.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">2. Free Trial</h2>
            <p>All new accounts start with a 7-day free trial that includes access to premium features. No payment is required during the trial period, so no refund is applicable. We encourage you to fully explore the platform during your trial before subscribing.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">3. Refund Eligibility</h2>
            <p className="mb-3">You are eligible for a full refund if:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>You request a refund within <strong className="text-gray-900 dark:text-white">7 days</strong> of your first paid subscription charge</li>
              <li>You experience a significant technical issue that we are unable to resolve</li>
              <li>You were charged after cancelling your subscription due to a billing error</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">4. Non-Refundable Situations</h2>
            <p className="mb-3">Refunds are generally not provided for:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>Requests made more than 7 days after the billing date</li>
              <li>Partial months of service (subscriptions remain active until the end of the billing period)</li>
              <li>Accounts terminated for Terms of Service violations</li>
              <li>Downgrade differences (switching from a higher to a lower plan)</li>
              <li>Unused portions of annual subscriptions after the 7-day window</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">5. How to Request a Refund</h2>
            <p className="mb-3">To request a refund, contact our support team:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>Email <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a> with the subject line &quot;Refund Request&quot;</li>
              <li>Include your registered email address and the reason for your request</li>
            </ul>
            <p className="mt-3">We aim to process all refund requests within 5 business days. Approved refunds will be returned to your original payment method and may take 5–10 business days to appear on your statement.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">6. Cancellation</h2>
            <p>You can cancel your subscription at any time from the <strong className="text-gray-900 dark:text-white">Settings</strong> page in your dashboard. After cancellation:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li>You retain access to paid features until the end of your current billing period</li>
              <li>Your account will be downgraded to the Free plan after the period ends</li>
              <li>Your data will be preserved and available if you choose to resubscribe</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">7. Annual Subscriptions</h2>
            <p>For annual subscriptions, the 7-day refund window applies from the date of the annual charge. After the 7-day window, annual subscriptions are non-refundable but may be cancelled to prevent renewal.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">8. Contact Us</h2>
            <p>For any billing questions or concerns not covered here, contact us at <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
