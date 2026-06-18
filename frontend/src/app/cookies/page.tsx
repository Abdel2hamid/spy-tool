import Link from 'next/link';
import { Zap, ArrowLeft } from 'lucide-react';

export const metadata = { title: 'Cookie Policy — RankSpy' };

export default function CookiesPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Cookie Policy</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: June 18, 2026</p>

        <div className="prose prose-gray dark:prose-invert max-w-none space-y-8 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">1. What Are Cookies</h2>
            <p>Cookies are small text files stored on your device when you visit a website. They help the site remember your preferences and improve your browsing experience. RankSpy uses cookies to provide essential functionality and understand how you use our platform.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">2. Cookies We Use</h2>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-3 pr-4 font-semibold text-gray-900 dark:text-white">Cookie</th>
                    <th className="text-left py-3 pr-4 font-semibold text-gray-900 dark:text-white">Type</th>
                    <th className="text-left py-3 pr-4 font-semibold text-gray-900 dark:text-white">Purpose</th>
                    <th className="text-left py-3 font-semibold text-gray-900 dark:text-white">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  <tr>
                    <td className="py-3 pr-4 font-mono text-xs">auth_token</td>
                    <td className="py-3 pr-4">Essential</td>
                    <td className="py-3 pr-4">Keeps you logged in and authenticates API requests</td>
                    <td className="py-3">Session</td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4 font-mono text-xs">theme</td>
                    <td className="py-3 pr-4">Functional</td>
                    <td className="py-3 pr-4">Remembers your dark/light mode preference</td>
                    <td className="py-3">1 year</td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4 font-mono text-xs">sidebar_state</td>
                    <td className="py-3 pr-4">Functional</td>
                    <td className="py-3 pr-4">Remembers sidebar collapsed/expanded state</td>
                    <td className="py-3">1 year</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">3. Types of Cookies</h2>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Essential Cookies:</strong> Required for the platform to function. Without these, you cannot log in or use authenticated features. These cannot be disabled.</p>
            <p className="mb-3"><strong className="text-gray-900 dark:text-white">Functional Cookies:</strong> Used to remember your preferences (like theme). Disabling these will reset your preferences on each visit.</p>
            <p><strong className="text-gray-900 dark:text-white">Analytics Cookies:</strong> We do not currently use third-party analytics cookies. If we add analytics in the future, we will update this policy and notify you.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">4. Third-Party Cookies</h2>
            <p>RankSpy does not use third-party advertising or tracking cookies. We do not share cookie data with advertisers or data brokers. If our payment processor sets cookies during checkout, those are governed by their own cookie policy.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">5. Managing Cookies</h2>
            <p className="mb-3">You can control cookies through your browser settings. Most browsers allow you to:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li>View what cookies are stored and delete them individually</li>
              <li>Block third-party cookies</li>
              <li>Block cookies from specific sites</li>
              <li>Block all cookies</li>
              <li>Delete all cookies when you close the browser</li>
            </ul>
            <p className="mt-3">Please note that blocking essential cookies will prevent you from using the RankSpy platform.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">6. Local Storage</h2>
            <p>In addition to cookies, we use browser local storage to cache non-sensitive UI preferences and temporary data for performance. Local storage data does not leave your browser and is not sent to our servers with requests.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">7. Changes to This Policy</h2>
            <p>We may update this Cookie Policy to reflect changes in technology or legal requirements. Material changes will be communicated through the platform or by updating this page.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">8. Contact Us</h2>
            <p>If you have questions about our use of cookies, contact us at <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
