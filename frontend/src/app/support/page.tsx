import Link from 'next/link';
import { Zap, ArrowLeft, Mail, MessageCircle, FileText, Clock, Shield } from 'lucide-react';

export const metadata = { title: 'Support — RankSpy' };

export default function SupportPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Support Center</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">We&apos;re here to help you get the most out of RankSpy.</p>

        {/* Contact cards */}
        <div className="grid sm:grid-cols-2 gap-4 mb-12">
          <a
            href="mailto:support@rankspy.app"
            className="group flex items-start gap-4 rounded-xl border border-gray-200 dark:border-gray-800 p-6 hover:border-indigo-300 dark:hover:border-indigo-700 hover:shadow-md transition-all"
          >
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900 transition">
              <Mail className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Email Support</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">Send us a message and we&apos;ll get back to you within 24 hours.</p>
              <p className="mt-2 text-sm font-medium text-indigo-600 dark:text-indigo-400">support@rankspy.app</p>
            </div>
          </a>

          <a
            href="mailto:support@rankspy.app?subject=Bug Report"
            className="group flex items-start gap-4 rounded-xl border border-gray-200 dark:border-gray-800 p-6 hover:border-indigo-300 dark:hover:border-indigo-700 hover:shadow-md transition-all"
          >
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-orange-50 dark:bg-orange-950 text-orange-600 dark:text-orange-400 group-hover:bg-orange-100 dark:group-hover:bg-orange-900 transition">
              <MessageCircle className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Report a Bug</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">Found something broken? Let us know and we&apos;ll fix it quickly.</p>
              <p className="mt-2 text-sm font-medium text-orange-600 dark:text-orange-400">Report an issue</p>
            </div>
          </a>
        </div>

        {/* Response times */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-6 mb-12">
          <div className="flex items-center gap-3 mb-4">
            <Clock className="h-5 w-5 text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Response Times</h2>
          </div>
          <div className="grid sm:grid-cols-3 gap-4 text-sm">
            <div className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4">
              <p className="font-medium text-gray-900 dark:text-white mb-1">Starter Plan</p>
              <p className="text-gray-500 dark:text-gray-400">Within 48 hours</p>
            </div>
            <div className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4">
              <p className="font-medium text-gray-900 dark:text-white mb-1">Pro Plan</p>
              <p className="text-gray-500 dark:text-gray-400">Within 24 hours</p>
            </div>
            <div className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4">
              <p className="font-medium text-gray-900 dark:text-white mb-1">Enterprise Plan</p>
              <p className="text-gray-500 dark:text-gray-400">Priority — within 4 hours</p>
            </div>
          </div>
        </div>

        {/* FAQ quick links */}
        <div className="mb-12">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Common Questions</h2>
          <div className="space-y-3">
            {[
              { q: 'How do I cancel my subscription?', a: 'Go to Settings in your dashboard and click "Cancel Subscription". You\'ll retain access until the end of your billing period.' },
              { q: 'Can I change my plan?', a: 'Yes! You can upgrade or downgrade anytime from the Settings page. Changes take effect immediately for upgrades, and at the next billing cycle for downgrades.' },
              { q: 'How do I reset my password?', a: 'Click "Forgot password?" on the login page, or go to Settings > Security in your dashboard.' },
              { q: 'What happens when my trial ends?', a: 'Your account will be downgraded to the Free plan with limited features. Your data is preserved — upgrade anytime to regain access.' },
              { q: 'Can I export my data?', a: 'Yes, paid plans include data export functionality. You can export keyword data, rankings, and app analytics as CSV files.' },
              { q: 'How do I request a refund?', a: 'Email support@rankspy.app within 7 days of your first charge. See our Refund Policy for full details.' },
            ].map((item) => (
              <details key={item.q} className="group rounded-lg border border-gray-200 dark:border-gray-800">
                <summary className="flex cursor-pointer items-center justify-between px-4 py-3 text-sm font-medium text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-900 rounded-lg transition">
                  {item.q}
                  <span className="ml-2 text-gray-400 transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="px-4 pb-3 text-sm text-gray-600 dark:text-gray-400">{item.a}</p>
              </details>
            ))}
          </div>
        </div>

        {/* Related links */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <div className="flex items-center gap-3 mb-4">
            <FileText className="h-5 w-5 text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Policies &amp; Legal</h2>
          </div>
          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            <Link href="/terms" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition">
              <Shield className="h-4 w-4" />
              Terms of Service
            </Link>
            <Link href="/privacy" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition">
              <Shield className="h-4 w-4" />
              Privacy Policy
            </Link>
            <Link href="/cookies" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition">
              <Shield className="h-4 w-4" />
              Cookie Policy
            </Link>
            <Link href="/refund" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition">
              <Shield className="h-4 w-4" />
              Refund Policy
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
