import Link from 'next/link';
import { Zap, ArrowLeft, Database, Globe, Search, BarChart3, Star, AlertTriangle } from 'lucide-react';

export const metadata = { title: 'Data Sources & Methodology — RankSpy' };

export default function DataSourcesPage() {
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Data Sources &amp; Methodology</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">How we collect, process, and present App Store intelligence.</p>

        <div className="prose prose-gray dark:prose-invert max-w-none space-y-10 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          {/* Overview */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Overview</h2>
            <p>
              RankSpy aggregates publicly available data from the Apple App Store to provide market intelligence, ranking analytics, and competitive insights. We do not access any private, confidential, or proprietary developer data.
            </p>
          </section>

          {/* Data we collect */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">What Data We Collect</h2>
            <div className="grid sm:grid-cols-2 gap-4 not-prose">
              {[
                { icon: Globe, title: 'App Metadata', desc: 'App names, descriptions, icons, screenshots, developer info, pricing, and content ratings as publicly listed on the App Store.' },
                { icon: BarChart3, title: 'Category Rankings', desc: 'Daily snapshots of top charts across categories and countries, sourced from publicly visible App Store rankings.' },
                { icon: Search, title: 'Keyword Search Results', desc: 'Search result positions for specific keywords, reflecting what any user would see when searching the App Store.' },
                { icon: Star, title: 'User Reviews & Ratings', desc: 'Publicly posted user reviews and aggregate rating data as displayed on the App Store.' },
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

          {/* Methodology */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Our Methodology</h2>
            <p className="mb-3">
              <strong className="text-gray-900 dark:text-white">Data Collection:</strong> Our automated systems periodically query the Apple App Store&apos;s public interfaces to capture app listings, rankings, search results, and reviews. Collection frequency varies by data type &mdash; rankings are updated daily, while app metadata is refreshed as changes are detected.
            </p>
            <p className="mb-3">
              <strong className="text-gray-900 dark:text-white">Processing &amp; Analysis:</strong> Raw data is cleaned, normalized, and stored in our database. We compute derived metrics such as ranking velocity, trending scores, keyword difficulty estimates, and opportunity scores using proprietary algorithms.
            </p>
            <p className="mb-3">
              <strong className="text-gray-900 dark:text-white">AI-Powered Insights:</strong> We use AI models to analyze review sentiment, generate app ideas, summarize market trends, and surface competitive intelligence. AI-generated content is clearly indicated within the platform.
            </p>
            <p>
              <strong className="text-gray-900 dark:text-white">Data Freshness:</strong> We strive to keep all data as current as possible. Rankings and trending data are typically updated daily. Historical data is retained to power trend analysis and trajectory charts.
            </p>
          </section>

          {/* Accuracy */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Accuracy &amp; Limitations</h2>
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 not-prose mb-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800 dark:text-amber-300">
                  <p className="font-semibold mb-1">Important Disclaimer</p>
                  <p>RankSpy data is provided for informational purposes only. While we strive for accuracy, App Store data can change rapidly and our metrics are estimates based on publicly available information. Always verify critical business decisions with primary sources.</p>
                </div>
              </div>
            </div>
            <ul className="list-disc pl-5 space-y-2">
              <li>Keyword search volume and difficulty are <strong className="text-gray-900 dark:text-white">estimates</strong> derived from our proprietary models, not official Apple data.</li>
              <li>Rankings may have a slight delay compared to real-time App Store positions.</li>
              <li>Review data reflects publicly available reviews and may not include all reviews if Apple filters some from public display.</li>
              <li>AI-generated insights are based on data patterns and should be validated before acting on them.</li>
            </ul>
          </section>

          {/* Apple disclaimer */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Apple Trademark Disclaimer</h2>
            <p>
              Apple, the Apple logo, iPhone, iPad, and App Store are trademarks of Apple Inc., registered in the U.S. and other countries. RankSpy is an independent product and is <strong className="text-gray-900 dark:text-white">not affiliated with, endorsed by, or sponsored by Apple Inc.</strong>
            </p>
            <p className="mt-3">
              All App Store data presented on RankSpy is sourced from publicly available information. We respect Apple&apos;s intellectual property and terms of service.
            </p>
          </section>

          {/* Data usage */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Your Data Usage</h2>
            <p>
              For information about how we handle your personal data (account information, usage analytics, etc.), please refer to our <Link href="/privacy" className="text-indigo-600 dark:text-indigo-400 hover:underline">Privacy Policy</Link>.
            </p>
            <p className="mt-3">
              If you are an app developer and believe your app data is being displayed incorrectly, or if you wish to request corrections, please contact us at <a href="mailto:support@rankspy.app" className="text-indigo-600 dark:text-indigo-400 hover:underline">support@rankspy.app</a>.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
