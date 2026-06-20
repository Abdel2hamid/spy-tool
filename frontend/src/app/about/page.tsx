import Link from 'next/link';
import { Zap, ArrowLeft, Target, Eye, Shield, BarChart3, Brain, Rocket } from 'lucide-react';

export const metadata = { title: 'About — RankSpy' };

export default function AboutPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">About RankSpy</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">AI-powered App Store intelligence for developers, marketers, and entrepreneurs.</p>

        <div className="prose prose-gray dark:prose-invert max-w-none space-y-10 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          {/* Mission */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Our Mission</h2>
            <p>
              RankSpy was built to democratize App Store intelligence. We believe every app developer &mdash; whether indie or enterprise &mdash; deserves access to the same market insights that big studios use to make strategic decisions.
            </p>
            <p className="mt-3">
              Our platform monitors the Apple App Store, surfaces competitive intelligence, tracks keyword rankings, and uses AI to generate actionable opportunities &mdash; all in one place.
            </p>
          </section>

          {/* What we do */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">What We Do</h2>
            <div className="grid sm:grid-cols-2 gap-4 not-prose">
              {[
                { icon: BarChart3, title: 'Ranking Tracker', desc: 'Track app positions across categories and countries with daily updates.' },
                { icon: Target, title: 'Keyword Intelligence', desc: 'Discover high-opportunity keywords with search volume and competition metrics.' },
                { icon: Brain, title: 'AI-Powered Insights', desc: 'Get AI-generated app ideas, review summaries, and market opportunities.' },
                { icon: Eye, title: 'Competitor Monitoring', desc: 'Monitor competitor apps, compare rankings, and spot market shifts.' },
                { icon: Rocket, title: 'Trending Discovery', desc: 'Find apps that are blowing up and trending before your competitors do.' },
                { icon: Shield, title: 'Secure & Private', desc: 'Your data is encrypted, never shared, and you control your account.' },
              ].map((item) => (
                <div key={item.title} className="flex items-start gap-3 p-4 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-950 flex-shrink-0">
                    <item.icon className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-white text-sm">{item.title}</h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* How it works */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">How It Works</h2>
            <p>
              RankSpy continuously collects publicly available data from the Apple App Store. Our systems aggregate app metadata, category rankings, keyword search results, and user reviews to build a comprehensive picture of the App Store landscape.
            </p>
            <p className="mt-3">
              This data is processed through our AI models to surface trends, detect opportunities, and generate insights that would take hours of manual research. All data we collect is publicly available information &mdash; we never access private developer accounts or confidential data.
            </p>
          </section>

          {/* Transparency */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Our Commitment to Transparency</h2>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong className="text-gray-900 dark:text-white">Data Sources:</strong> We only use publicly available App Store data. See our <Link href="/data-sources" className="text-indigo-600 dark:text-indigo-400 hover:underline">Data Sources</Link> page for details.</li>
              <li><strong className="text-gray-900 dark:text-white">Privacy First:</strong> We collect minimal personal data and never sell it. Read our <Link href="/privacy" className="text-indigo-600 dark:text-indigo-400 hover:underline">Privacy Policy</Link>.</li>
              <li><strong className="text-gray-900 dark:text-white">Fair Pricing:</strong> All plans include a 7-day free trial. Cancel anytime. See our <Link href="/refund" className="text-indigo-600 dark:text-indigo-400 hover:underline">Refund Policy</Link>.</li>
              <li><strong className="text-gray-900 dark:text-white">No Affiliation:</strong> RankSpy is an independent product. We are not affiliated with, endorsed by, or sponsored by Apple Inc.</li>
            </ul>
          </section>

          {/* Contact */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Get in Touch</h2>
            <p>
              We&apos;re always happy to hear from our users. Whether you have a question, feedback, or just want to say hello:
            </p>
            <ul className="list-disc pl-5 space-y-2 mt-3">
              <li>Email: <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a></li>
              <li>Support Center: <Link href="/support" className="text-indigo-600 dark:text-indigo-400 hover:underline">rankspy.app/support</Link></li>
              <li>Contact Page: <Link href="/contact" className="text-indigo-600 dark:text-indigo-400 hover:underline">rankspy.app/contact</Link></li>
            </ul>
          </section>
        </div>
      </main>
    </div>
  );
}
