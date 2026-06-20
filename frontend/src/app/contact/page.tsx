import Link from 'next/link';
import { Zap, ArrowLeft, Mail, Clock, Shield, MessageCircle } from 'lucide-react';

export const metadata = { title: 'Contact Us — RankSpy' };

export default function ContactPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Contact Us</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Have a question, feedback, or need help? We&apos;d love to hear from you.</p>

        <div className="grid md:grid-cols-2 gap-10">
          {/* Contact info */}
          <div>
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-950 flex-shrink-0">
                  <Mail className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Email Support</h3>
                  <a href="mailto:support@rankspy.app" className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a>
                  <p className="text-xs text-gray-500 mt-1">For general inquiries, technical support, and account questions.</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-950 flex-shrink-0">
                  <MessageCircle className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Billing &amp; Subscriptions</h3>
                  <a href="mailto:billing@rankspy.app" className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline">billing@rankspy.app</a>
                  <p className="text-xs text-gray-500 mt-1">For payment issues, refund requests, and subscription management.</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-950 flex-shrink-0">
                  <Clock className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Response Time</h3>
                  <p className="text-sm text-gray-700 dark:text-gray-300">We typically respond within 24 hours on business days.</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-950 flex-shrink-0">
                  <Shield className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Data &amp; Privacy</h3>
                  <a href="mailto:privacy@rankspy.app" className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline">privacy@rankspy.app</a>
                  <p className="text-xs text-gray-500 mt-1">For GDPR requests, data deletion, or privacy-related concerns.</p>
                </div>
              </div>
            </div>

            <div className="mt-10 p-5 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2 text-sm">Helpful Links</h3>
              <ul className="space-y-2 text-sm">
                <li><Link href="/support" className="text-indigo-600 dark:text-indigo-400 hover:underline">Support Center</Link></li>
                <li><Link href="/refund" className="text-indigo-600 dark:text-indigo-400 hover:underline">Refund Policy</Link></li>
                <li><Link href="/privacy" className="text-indigo-600 dark:text-indigo-400 hover:underline">Privacy Policy</Link></li>
                <li><Link href="/terms" className="text-indigo-600 dark:text-indigo-400 hover:underline">Terms of Service</Link></li>
              </ul>
            </div>
          </div>

          {/* Contact form */}
          <div>
            <form
              action="mailto:support@rankspy.app"
              method="POST"
              encType="text/plain"
              className="space-y-5"
            >
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-900 dark:text-white mb-1.5">Name</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  required
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3.5 py-2.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
                  placeholder="Your name"
                />
              </div>

              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-900 dark:text-white mb-1.5">Email</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  required
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3.5 py-2.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label htmlFor="subject" className="block text-sm font-medium text-gray-900 dark:text-white mb-1.5">Subject</label>
                <select
                  id="subject"
                  name="subject"
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3.5 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
                >
                  <option value="general">General Inquiry</option>
                  <option value="support">Technical Support</option>
                  <option value="billing">Billing Question</option>
                  <option value="feature">Feature Request</option>
                  <option value="bug">Bug Report</option>
                  <option value="privacy">Privacy / Data Request</option>
                </select>
              </div>

              <div>
                <label htmlFor="message" className="block text-sm font-medium text-gray-900 dark:text-white mb-1.5">Message</label>
                <textarea
                  id="message"
                  name="message"
                  rows={5}
                  required
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3.5 py-2.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition resize-none"
                  placeholder="How can we help you?"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg transition text-sm"
              >
                Send Message
              </button>

              <p className="text-xs text-gray-500 text-center">
                Or email us directly at <a href="mailto:support@rankspy.app" className="text-indigo-600 hover:underline">support@rankspy.app</a>
              </p>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
