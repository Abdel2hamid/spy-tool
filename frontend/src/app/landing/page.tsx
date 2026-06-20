'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
  Zap,
  TrendingUp,
  Search,
  Brain,
  BarChart3,
  Target,
  Rocket,
  Star,
  Check,
  ArrowRight,
  LineChart,
  Smartphone,
  Eye,
  Lightbulb,
  Flame,
  Crown,
  ChevronDown,
  Menu,
  Shield,
  CreditCard,
  Lock,
  Mail,
  X,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Scroll-triggered animation
// ---------------------------------------------------------------------------

function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.unobserve(el); } },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);

  return { ref, visible };
}

function AnimateIn({
  children,
  className = '',
  delay = 0,
  from = 'bottom',
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  from?: 'bottom' | 'left' | 'right' | 'scale';
}) {
  const { ref, visible } = useInView(0.1);

  const baseTransform = {
    bottom: 'translate3d(0, 32px, 0)',
    left: 'translate3d(-32px, 0, 0)',
    right: 'translate3d(32px, 0, 0)',
    scale: 'scale(0.95)',
  }[from];

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translate3d(0,0,0) scale(1)' : baseTransform,
        transition: `opacity 0.6s cubic-bezier(0.16,1,0.3,1) ${delay}s, transform 0.6s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated counter
// ---------------------------------------------------------------------------

function AnimatedCounter({ value }: { value: string }) {
  const { ref, visible } = useInView(0.3);
  const [display, setDisplay] = useState('0');
  const numericPart = value.replace(/[^0-9]/g, '');

  useEffect(() => {
    if (!visible || !numericPart) { setDisplay(value); return; }
    const target = parseInt(numericPart, 10);
    const duration = 1500;
    const start = performance.now();

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(target * eased);

      if (target >= 1000) {
        setDisplay(current >= 1000000 ? `${Math.round(current / 1000000)}M` : current >= 1000 ? `${Math.round(current / 1000)}K` : String(current));
      } else {
        setDisplay(String(current));
      }

      if (progress < 1) requestAnimationFrame(tick);
      else setDisplay(value);
    }

    requestAnimationFrame(tick);
  }, [visible, value, numericPart]);

  return <span ref={ref}>{display}</span>;
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: Brain,
    title: 'AI Review Intelligence',
    description: 'Extracts feature requests, competitor insights, and sentiment from thousands of reviews automatically.',
    gradient: 'from-violet-500 to-purple-600',
  },
  {
    icon: Lightbulb,
    title: 'AI App Idea Generator',
    description: 'Synthesizes app ideas from competitive signals, market gaps, and trending niches with opportunity scores.',
    gradient: 'from-amber-500 to-orange-600',
  },
  {
    icon: TrendingUp,
    title: 'Blowing Up Detection',
    description: '6-component algorithm catches emerging apps before they go viral. Get early signals on breakout hits.',
    gradient: 'from-rose-500 to-red-600',
  },
  {
    icon: Search,
    title: 'Keyword Intelligence',
    description: 'Keyword discovery, rank tracking, gap analysis, competitor mining, and difficulty scoring in one suite.',
    gradient: 'from-blue-500 to-cyan-600',
  },
  {
    icon: Target,
    title: 'Niche Radar',
    description: 'Detects emerging micro-niches via keyword and ranking anomalies. Find underserved markets first.',
    gradient: 'from-emerald-500 to-green-600',
  },
  {
    icon: BarChart3,
    title: 'Download & Revenue Estimates',
    description: '4-layer ensemble model using rank curves, review velocity, and momentum for accurate estimates.',
    gradient: 'from-indigo-500 to-blue-600',
  },
  {
    icon: LineChart,
    title: 'Rank Tracking & History',
    description: 'Full chart position history across 21 App Store categories. Track your own and competitor rankings.',
    gradient: 'from-teal-500 to-cyan-600',
  },
  {
    icon: Eye,
    title: 'Daily Opportunities',
    description: 'Curated keyword gaps, app ideas, and emerging niches delivered daily with diversity logic.',
    gradient: 'from-pink-500 to-rose-600',
  },
  {
    icon: Flame,
    title: 'Trending & New Releases',
    description: 'Real-time trending apps with momentum scores and daily new release tracking across all categories.',
    gradient: 'from-orange-500 to-red-600',
  },
];

const PLANS = [
  {
    code: 'starter',
    name: 'Starter',
    price: '$19.99',
    period: '/month',
    description: 'Perfect for indie developers and small teams getting started with ASO.',
    features: [
      '100 app imports / month',
      '200 keyword refreshes / month',
      '100 AI requests / month',
      '50 exports / month',
      'All premium features included',
      'Email support',
    ],
    cta: 'Start Free Trial',
    popular: false,
  },
  {
    code: 'pro',
    name: 'Pro',
    price: '$49.99',
    period: '/month',
    description: 'For serious ASO professionals and growing teams who need unlimited access.',
    features: [
      'Unlimited app imports',
      'Unlimited keyword refreshes',
      'Unlimited AI requests',
      'Unlimited exports',
      'All premium features included',
      'Priority email support',
    ],
    cta: 'Start Free Trial',
    popular: true,
  },
];

const STATS = [
  { value: '2M+', label: 'Apps Tracked' },
  { value: '500K+', label: 'Keywords Monitored' },
  { value: '21', label: 'Categories Covered' },
  { value: '24/7', label: 'Real-time Updates' },
];

const TESTIMONIALS = [
  {
    quote: "RankSpy's AI idea generator found me a niche nobody was targeting. My app hit #3 in its category within 2 weeks.",
    name: 'Sarah K.',
    role: 'Indie Developer',
    avatar: 'S',
    color: 'from-violet-400 to-purple-500',
  },
  {
    quote: "We replaced Sensor Tower with RankSpy. The keyword intelligence is on par, the AI insights are unique, and we save thousands per month.",
    name: 'Marcus T.',
    role: 'ASO Lead at Appify',
    avatar: 'M',
    color: 'from-blue-400 to-indigo-500',
  },
  {
    quote: "The blowing-up detection caught a competitor's growth 10 days before anyone else noticed. That early signal was invaluable.",
    name: 'James L.',
    role: 'Growth Product Manager',
    avatar: 'J',
    color: 'from-emerald-400 to-teal-500',
  },
];

const FAQS = [
  {
    q: 'How does the 7-day free trial work?',
    a: 'Pick any plan and create your account. You get full access to all features for 7 days with no charge. After the trial, your subscription begins automatically at the plan price. You can cancel anytime before the trial ends to avoid being charged.',
  },
  {
    q: 'What happens when my trial ends?',
    a: 'Your subscription automatically renews at the selected plan price ($19.99/mo for Starter, $49.99/mo for Pro). You\'ll be charged on the same payment method provided at signup. You can cancel anytime from your account Settings page.',
  },
  {
    q: 'Can I cancel my subscription anytime?',
    a: 'Yes. Cancel anytime from Settings > Billing > Manage Billing Portal. No cancellation fees, no long-term contracts. You keep access until the end of your current billing period.',
  },
  {
    q: 'What is your refund policy?',
    a: 'We offer full refunds within 7 days of your first paid charge. Contact support@rankspy.app with your request. See our full Refund Policy for details.',
  },
  {
    q: 'What makes RankSpy different from Sensor Tower or data.ai?',
    a: "We're the first ASO tool with AI-powered intelligence. While others give you raw data, we generate actionable app ideas, detect niches automatically, and analyze reviews with AI. Plus, our plans start at $19.99/mo vs $149+/mo.",
  },
  {
    q: 'How accurate are the download and revenue estimates?',
    a: 'Our 4-layer ensemble model combines rank curves, review velocity, keyword visibility, and momentum signals. While no third-party estimate is perfect, our model is continuously calibrated against real-world data.',
  },
  {
    q: 'Can I track my competitors\' apps?',
    a: 'Yes. Add any app to your tracked list and monitor rank changes, review sentiment, keyword positions, and growth signals in real-time.',
  },
  {
    q: 'How is my payment information handled?',
    a: 'All payments are securely processed by Stripe, a PCI Level 1 certified payment processor. We never store your credit card details on our servers.',
  },
];

const COMPARISONS = [
  { feature: 'AI-Powered App Ideas', us: true, others: false },
  { feature: 'LLM Review Analysis', us: true, others: false },
  { feature: 'Niche Radar', us: true, others: false },
  { feature: 'Keyword Tracking', us: true, others: true },
  { feature: 'Rank Monitoring', us: true, others: true },
  { feature: 'Download Estimates', us: true, others: true },
  { feature: 'Blowing-Up Detection', us: true, others: false },
  { feature: 'Starting Price', us: '$19.99/mo', others: '$149/mo' },
];

// ---------------------------------------------------------------------------
// Navbar
// ---------------------------------------------------------------------------

function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-white/90 dark:bg-gray-950/90 backdrop-blur-xl border-b border-gray-200/60 dark:border-gray-800/60 shadow-sm'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </div>

          <div className="hidden md:flex items-center gap-8">
            {['Features', 'Pricing', 'Compare', 'FAQ'].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase()}`}
                className="text-sm text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors"
              >
                {item}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white px-4 py-2 rounded-lg transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-5 py-2 rounded-lg transition-all shadow-sm hover:shadow-md hover:-translate-y-px"
            >
              Start Free Trial
            </Link>
          </div>

          <button onClick={() => setMobileOpen(!mobileOpen)} className="md:hidden p-2 text-gray-500">
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="md:hidden pb-4 border-t border-gray-100 dark:border-gray-800 mt-2 pt-4 space-y-2 bg-white/95 dark:bg-gray-950/95 backdrop-blur-xl rounded-b-xl">
            {['Features', 'Pricing', 'Compare', 'FAQ'].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`} onClick={() => setMobileOpen(false)} className="block text-sm text-gray-600 dark:text-gray-400 py-2 px-1">
                {item}
              </a>
            ))}
            <div className="flex gap-3 pt-3">
              <Link href="/login" className="flex-1 text-center text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 px-4 py-2.5 rounded-lg">
                Sign In
              </Link>
              <Link href="/signup" className="flex-1 text-center text-sm font-medium text-white bg-indigo-600 px-4 py-2.5 rounded-lg">
                Start Free Trial
              </Link>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function HeroSection() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <section className="relative pt-28 pb-16 sm:pt-36 sm:pb-24 overflow-hidden">
      {/* Soft gradient background */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] bg-gradient-to-b from-indigo-50/80 via-purple-50/40 to-transparent dark:from-indigo-950/30 dark:via-purple-950/15 rounded-full blur-3xl" />
        <div className="absolute top-10 right-0 w-[350px] h-[350px] bg-gradient-to-bl from-sky-50/50 to-transparent dark:from-sky-950/15 rounded-full blur-3xl" />
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(24px)',
            transition: 'opacity 0.7s cubic-bezier(0.16,1,0.3,1) 0.1s, transform 0.7s cubic-bezier(0.16,1,0.3,1) 0.1s',
          }}
        >
          {/* Trust badge */}
          <div className="inline-flex items-center gap-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-full px-4 py-1.5 mb-8 shadow-sm">
            <div className="flex items-center gap-0.5">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="w-3 h-3 text-amber-400 fill-amber-400" />
              ))}
            </div>
            <span className="text-xs text-gray-600 dark:text-gray-400 font-medium">Trusted by app developers worldwide</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-gray-900 dark:text-white leading-[1.1] max-w-4xl mx-auto">
            AI-Powered{' '}
            <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              App Store Intelligence
            </span>
          </h1>
        </div>

        <div
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(24px)',
            transition: 'opacity 0.7s cubic-bezier(0.16,1,0.3,1) 0.25s, transform 0.7s cubic-bezier(0.16,1,0.3,1) 0.25s',
          }}
        >
          <p className="mt-6 text-lg text-gray-500 dark:text-gray-400 max-w-2xl mx-auto leading-relaxed">
            Discover winning app ideas, track competitor rankings, and surface keyword opportunities with AI — before anyone else.
          </p>
        </div>

        <div
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(24px)',
            transition: 'opacity 0.7s cubic-bezier(0.16,1,0.3,1) 0.4s, transform 0.7s cubic-bezier(0.16,1,0.3,1) 0.4s',
          }}
        >
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/signup"
              className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-8 py-3.5 rounded-xl text-base transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5"
            >
              Start 7-Day Free Trial
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <a
              href="#features"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 text-gray-600 dark:text-gray-400 font-medium px-8 py-3.5 rounded-xl text-base border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-900 transition-all hover:-translate-y-0.5"
            >
              See How It Works
              <ChevronDown className="w-4 h-4" />
            </a>
          </div>

          <p className="mt-4 text-sm text-gray-400">
            No credit card required &middot; 7-day free trial &middot; Cancel anytime
          </p>
        </div>

        {/* Stats */}
        <div className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-3xl mx-auto">
          {STATS.map((s, i) => (
            <AnimateIn key={s.label} from="bottom" delay={0.5 + i * 0.08}>
              <div className="rounded-xl bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 px-4 py-4 shadow-sm hover:shadow-md transition-shadow">
                <p className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
                  <AnimatedCounter value={s.value} />
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{s.label}</p>
              </div>
            </AnimateIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Trust Bar
// ---------------------------------------------------------------------------

function TrustBar() {
  return (
    <section className="py-10 border-y border-gray-100 dark:border-gray-800/50 bg-gray-50/50 dark:bg-gray-900/20">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12">
          {[
            { icon: Shield, label: 'SOC 2 Compliant Infra' },
            { icon: Lock, label: 'TLS Encryption' },
            { icon: CreditCard, label: 'Secured by Stripe' },
            { icon: Mail, label: '24h Support Response' },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2.5 text-gray-400 dark:text-gray-500">
              <item.icon className="w-4 h-4" />
              <span className="text-xs font-medium tracking-wide uppercase">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Features
// ---------------------------------------------------------------------------

function FeaturesSection() {
  return (
    <section id="features" className="py-20 sm:py-28">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">Features</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Everything You Need to Win the App Store
          </h2>
          <p className="mt-4 text-gray-500 dark:text-gray-400">
            From AI-powered idea generation to real-time rank tracking — one platform for your entire ASO workflow.
          </p>
        </AnimateIn>

        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <AnimateIn key={f.title} delay={i * 0.06} from={i % 3 === 0 ? 'left' : i % 3 === 2 ? 'right' : 'bottom'}>
              <div className="group rounded-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 hover:border-gray-200 dark:hover:border-gray-700 hover:shadow-lg transition-all duration-300 h-full">
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${f.gradient} flex items-center justify-center mb-4 shadow-sm group-hover:scale-105 transition-transform`}>
                  <f.icon className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">{f.title}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">{f.description}</p>
              </div>
            </AnimateIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// How It Works
// ---------------------------------------------------------------------------

function HowItWorksSection() {
  const steps = [
    { num: '01', title: 'Import or Discover Apps', desc: 'Search the App Store or import apps by URL. Our engine indexes 2M+ apps across 21 categories.', icon: Smartphone },
    { num: '02', title: 'AI Analyzes Everything', desc: 'AI processes reviews, rankings, keywords, and market signals to surface actionable intelligence.', icon: Brain },
    { num: '03', title: 'Get Opportunities Daily', desc: 'Receive curated keyword gaps, app ideas, trending niches, and growth signals every day.', icon: Rocket },
    { num: '04', title: 'Build & Grow', desc: 'Use AI insights to build apps users want, optimized for discovery from day one.', icon: TrendingUp },
  ];

  return (
    <section className="py-20 sm:py-28 bg-gradient-to-b from-gray-50/80 to-white dark:from-gray-900/30 dark:to-gray-950">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">How It Works</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            From Data to App Ideas in Minutes
          </h2>
        </AnimateIn>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <AnimateIn key={s.num} delay={i * 0.12} from="bottom">
              <div className="relative text-center group">
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-10 left-[60%] w-[80%] h-px bg-gradient-to-r from-gray-200 to-transparent dark:from-gray-700" />
                )}
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm mb-5 group-hover:shadow-md group-hover:border-indigo-100 dark:group-hover:border-indigo-900 group-hover:-translate-y-1 transition-all duration-300">
                  <s.icon className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400 mb-2 tracking-wide">{s.num}</div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">{s.title}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">{s.desc}</p>
              </div>
            </AnimateIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Compare
// ---------------------------------------------------------------------------

function CompareSection() {
  const { ref, visible } = useInView(0.1);

  return (
    <section id="compare" className="py-20 sm:py-28">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-12">
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">Compare</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Why Teams Switch to RankSpy
          </h2>
          <p className="mt-4 text-gray-500 dark:text-gray-400">
            More features, AI-powered intelligence, and a fraction of the cost.
          </p>
        </AnimateIn>

        <div ref={ref} className="rounded-2xl border border-gray-100 dark:border-gray-800 overflow-hidden shadow-sm">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-900/80">
                <th className="px-5 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Feature</th>
                <th className="px-5 py-4 text-center text-sm font-semibold text-indigo-600 dark:text-indigo-400">
                  <div className="flex items-center justify-center gap-1.5">
                    <Zap className="w-3.5 h-3.5" /> RankSpy
                  </div>
                </th>
                <th className="px-5 py-4 text-center text-sm font-semibold text-gray-400">Others</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
              {COMPARISONS.map((row, i) => (
                <tr
                  key={row.feature}
                  className="bg-white dark:bg-gray-950"
                  style={{
                    opacity: visible ? 1 : 0,
                    transform: visible ? 'translateX(0)' : 'translateX(-16px)',
                    transition: `opacity 0.4s ease ${i * 0.06}s, transform 0.4s ease ${i * 0.06}s`,
                  }}
                >
                  <td className="px-5 py-3.5 text-sm text-gray-700 dark:text-gray-300">{row.feature}</td>
                  <td className="px-5 py-3.5 text-center">
                    {typeof row.us === 'boolean' ? (
                      <Check className="w-5 h-5 text-emerald-500 mx-auto" />
                    ) : (
                      <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{row.us}</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-center">
                    {typeof row.others === 'boolean' ? (
                      row.others ? <Check className="w-5 h-5 text-emerald-500 mx-auto" /> : <X className="w-5 h-5 text-gray-300 dark:text-gray-600 mx-auto" />
                    ) : (
                      <span className="text-sm text-gray-400">{row.others}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Pricing (Stripe-compliant)
// ---------------------------------------------------------------------------

function PricingSection() {
  return (
    <section id="pricing" className="py-20 sm:py-28 bg-gradient-to-b from-gray-50/80 to-white dark:from-gray-900/30 dark:to-gray-950">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-14">
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">Pricing</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Simple, Transparent Pricing
          </h2>
          <p className="mt-4 text-gray-500 dark:text-gray-400">
            Choose the plan that fits your needs. All plans include a 7-day free trial.
          </p>
        </AnimateIn>

        <div className="grid gap-8 md:grid-cols-2 max-w-3xl mx-auto">
          {PLANS.map((plan, i) => (
            <AnimateIn key={plan.name} delay={i * 0.1} from="scale">
              <div
                className={`relative rounded-2xl bg-white dark:bg-gray-900 p-7 flex flex-col h-full transition-all duration-300 ${
                  plan.popular
                    ? 'border-2 border-indigo-500 dark:border-indigo-400 shadow-lg shadow-indigo-500/10 hover:shadow-xl hover:shadow-indigo-500/15'
                    : 'border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700 hover:shadow-lg'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 bg-indigo-600 text-white text-xs font-semibold px-3.5 py-1 rounded-full">
                    <Crown className="w-3 h-3" /> Most Popular
                  </div>
                )}

                <div className="mb-5">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{plan.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{plan.description}</p>
                </div>

                <div className="flex items-baseline gap-1 mb-1">
                  <span className="text-4xl font-bold text-gray-900 dark:text-white">{plan.price}</span>
                  <span className="text-sm text-gray-400">{plan.period}</span>
                </div>
                <p className="text-xs text-gray-400 mb-6">Billed monthly in USD. Cancel anytime.</p>

                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5">
                      <Check className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-gray-600 dark:text-gray-300">{f}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={`/signup?plan=${plan.code}`}
                  className={`w-full text-center py-3 rounded-xl text-sm font-semibold transition-all hover:-translate-y-px ${
                    plan.popular
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-500/20 hover:shadow-md'
                      : 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-800 dark:hover:bg-gray-100'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            </AnimateIn>
          ))}
        </div>

        {/* Stripe compliance: trial terms, auto-renewal, refund, cancellation */}
        <AnimateIn className="mt-10 max-w-2xl mx-auto">
          <div className="rounded-xl bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 p-5">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4 text-gray-400" />
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Billing Details</span>
            </div>
            <ul className="space-y-2 text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
              <li className="flex items-start gap-2">
                <span className="text-gray-300 mt-0.5">&bull;</span>
                <span><strong className="text-gray-700 dark:text-gray-300">Free trial:</strong> 7 days of full access at no charge. No payment required upfront.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-gray-300 mt-0.5">&bull;</span>
                <span><strong className="text-gray-700 dark:text-gray-300">Auto-renewal:</strong> After your trial, your plan renews monthly at the listed price until you cancel.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-gray-300 mt-0.5">&bull;</span>
                <span><strong className="text-gray-700 dark:text-gray-300">Cancel anytime:</strong> Go to Settings &gt; Billing &gt; Manage Portal. No cancellation fees.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-gray-300 mt-0.5">&bull;</span>
                <span><strong className="text-gray-700 dark:text-gray-300">Refunds:</strong> Full refund within 7 days of your first charge. See our <Link href="/refund" className="text-indigo-600 dark:text-indigo-400 hover:underline">Refund Policy</Link>.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-gray-300 mt-0.5">&bull;</span>
                <span><strong className="text-gray-700 dark:text-gray-300">Payments:</strong> Securely processed by <a href="https://stripe.com" target="_blank" rel="noopener noreferrer" className="text-indigo-600 dark:text-indigo-400 hover:underline">Stripe</a>. We never store your card details.</span>
              </li>
            </ul>
          </div>
        </AnimateIn>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Testimonials
// ---------------------------------------------------------------------------

function TestimonialsSection() {
  return (
    <section className="py-20 sm:py-28">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">Testimonials</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Loved by Developers &amp; Growth Teams
          </h2>
        </AnimateIn>

        <div className="grid gap-6 md:grid-cols-3">
          {TESTIMONIALS.map((t, i) => (
            <AnimateIn key={t.name} delay={i * 0.12} from={i === 0 ? 'left' : i === 2 ? 'right' : 'bottom'}>
              <div className="rounded-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 hover:shadow-md transition-all duration-300 h-full flex flex-col">
                <div className="flex gap-0.5 mb-4">
                  {[...Array(5)].map((_, j) => (
                    <Star key={j} className="w-4 h-4 text-amber-400 fill-amber-400" />
                  ))}
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed mb-6 flex-1">&ldquo;{t.quote}&rdquo;</p>
                <div className="flex items-center gap-3 pt-4 border-t border-gray-50 dark:border-gray-800">
                  <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${t.color} flex items-center justify-center text-white text-sm font-bold shadow-sm`}>
                    {t.avatar}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{t.name}</p>
                    <p className="text-xs text-gray-400">{t.role}</p>
                  </div>
                </div>
              </div>
            </AnimateIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// FAQ
// ---------------------------------------------------------------------------

function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section id="faq" className="py-20 sm:py-28 bg-gradient-to-b from-gray-50/80 to-white dark:from-gray-900/30 dark:to-gray-950">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center mb-12">
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">FAQ</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Frequently Asked Questions
          </h2>
        </AnimateIn>

        <div className="space-y-3">
          {FAQS.map((faq, i) => (
            <AnimateIn key={i} delay={i * 0.06} from="bottom">
              <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden hover:border-gray-200 dark:hover:border-gray-700 transition-colors">
                <button
                  onClick={() => setOpenIndex(openIndex === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                >
                  <span className="text-sm font-medium text-gray-900 dark:text-white pr-4">{faq.q}</span>
                  <ChevronDown
                    className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform duration-200 ${openIndex === i ? 'rotate-180' : ''}`}
                  />
                </button>
                <div
                  className="overflow-hidden transition-all duration-200"
                  style={{
                    maxHeight: openIndex === i ? '300px' : '0',
                    opacity: openIndex === i ? 1 : 0,
                  }}
                >
                  <div className="px-5 pb-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">{faq.a}</p>
                  </div>
                </div>
              </div>
            </AnimateIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// CTA
// ---------------------------------------------------------------------------

function CTASection() {
  return (
    <section className="py-20 sm:py-28">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <AnimateIn from="scale">
          <div className="rounded-3xl bg-gradient-to-br from-indigo-600 via-indigo-700 to-purple-700 p-10 sm:p-16 relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(255,255,255,0.08),transparent_60%)]" />
            <div className="relative">
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                Ready to Find Your Next Big App?
              </h2>
              <p className="text-lg text-indigo-200 mb-8 max-w-xl mx-auto">
                Join developers using AI to discover App Store opportunities before the competition.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/signup"
                  className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-white text-indigo-700 font-semibold px-8 py-3.5 rounded-xl text-base hover:bg-indigo-50 transition-all shadow-lg hover:-translate-y-0.5"
                >
                  Start 7-Day Free Trial
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </div>
              <p className="mt-5 text-sm text-indigo-300">
                No credit card required &middot; Cancel anytime &middot; Plans from $19.99/mo
              </p>
            </div>
          </div>
        </AnimateIn>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="border-t border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-5">
          {/* Brand */}
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed max-w-xs mb-5">
              AI-powered App Store intelligence platform. Discover opportunities, track competitors, and build winning apps.
            </p>
            <a href="mailto:support@rankspy.app" className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline">
              support@rankspy.app
            </a>
          </div>

          {/* Links */}
          {[
            {
              title: 'Product',
              links: [
                { label: 'Features', href: '#features' },
                { label: 'Pricing', href: '#pricing' },
                { label: 'Compare', href: '#compare' },
                { label: 'FAQ', href: '#faq' },
              ],
            },
            {
              title: 'Company',
              links: [
                { label: 'About', href: '/about' },
                { label: 'Contact Us', href: '/contact' },
                { label: 'Support', href: '/support' },
                { label: 'Data Sources', href: '/data-sources' },
              ],
            },
            {
              title: 'Legal',
              links: [
                { label: 'Privacy Policy', href: '/privacy' },
                { label: 'Terms of Service', href: '/terms' },
                { label: 'Cookie Policy', href: '/cookies' },
                { label: 'Refund Policy', href: '/refund' },
              ],
            },
          ].map((section) => (
            <div key={section.title}>
              <h4 className="text-xs font-semibold text-gray-900 dark:text-white mb-4 uppercase tracking-wide">{section.title}</h4>
              <ul className="space-y-2.5">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <a href={link.href} className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-12 pt-8 border-t border-gray-100 dark:border-gray-800">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-4">
            <p className="text-xs text-gray-400">
              &copy; {new Date().getFullYear()} RankSpy. All rights reserved.
            </p>
            <div className="flex items-center gap-6 text-xs text-gray-400">
              <Link href="/privacy" className="hover:text-gray-600 dark:hover:text-gray-300 transition-colors">Privacy</Link>
              <Link href="/terms" className="hover:text-gray-600 dark:hover:text-gray-300 transition-colors">Terms</Link>
              <Link href="/refund" className="hover:text-gray-600 dark:hover:text-gray-300 transition-colors">Refunds</Link>
              <Link href="/contact" className="hover:text-gray-600 dark:hover:text-gray-300 transition-colors">Contact</Link>
            </div>
          </div>
          <p className="text-[11px] text-gray-300 dark:text-gray-700 text-center leading-relaxed">
            Payments securely processed by Stripe. All prices in USD. Subscriptions renew automatically and can be cancelled anytime.
            Apple and App Store are trademarks of Apple Inc. RankSpy is not affiliated with Apple Inc.
          </p>
        </div>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------
// Main Landing Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <style jsx global>{`
        @keyframes gradientShift {
          0%, 100% { background-position: 0% center; }
          50% { background-position: 100% center; }
        }
      `}</style>
      <Navbar />
      <HeroSection />
      <TrustBar />
      <FeaturesSection />
      <HowItWorksSection />
      <CompareSection />
      <PricingSection />
      <TestimonialsSection />
      <FAQSection />
      <CTASection />
      <Footer />
    </div>
  );
}
