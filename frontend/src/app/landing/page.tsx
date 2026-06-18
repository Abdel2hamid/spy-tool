'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
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
  X,
  ArrowRight,
  Users,
  LineChart,
  Smartphone,
  Eye,
  Lightbulb,
  Flame,
  Crown,
  ChevronDown,
  Menu,
  Twitter,
  Github,
  Linkedin,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Scroll-triggered animation hook
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

// Stagger children animation wrapper
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
    bottom: 'translate3d(0, 40px, 0)',
    left: 'translate3d(-40px, 0, 0)',
    right: 'translate3d(40px, 0, 0)',
    scale: 'scale(0.9)',
  }[from];

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translate3d(0,0,0) scale(1)' : baseTransform,
        transition: `opacity 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}s, transform 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated counter
// ---------------------------------------------------------------------------

function AnimatedCounter({ value, suffix = '' }: { value: string; suffix?: string }) {
  const { ref, visible } = useInView(0.3);
  const [display, setDisplay] = useState('0');
  const numericPart = value.replace(/[^0-9]/g, '');
  const prefix = value.replace(/[0-9+,]/g, '').replace(suffix, '');

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
        setDisplay(current >= 1000 ? `${Math.round(current / 1000)}${current >= 1000000 ? 'M' : 'K'}` : String(current));
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
    title: 'AI-Powered Review Intelligence',
    description: 'AI extracts feature requests, competitor comparisons, and pricing complaints from thousands of reviews automatically.',
    bg: 'bg-purple-50 dark:bg-purple-950/30',
    iconColor: 'text-purple-600 dark:text-purple-400',
  },
  {
    icon: Lightbulb,
    title: 'AI App Idea Generator',
    description: 'Automatically synthesizes app ideas from competitive signals, market gaps, and trending niches with opportunity scores.',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    iconColor: 'text-amber-600 dark:text-amber-400',
  },
  {
    icon: TrendingUp,
    title: 'Blowing Up Detection',
    description: '6-component scoring algorithm catches emerging apps before they go viral. Get early signals on the next breakout hit.',
    bg: 'bg-red-50 dark:bg-red-950/30',
    iconColor: 'text-red-600 dark:text-red-400',
  },
  {
    icon: Search,
    title: 'Keyword Intelligence Suite',
    description: '11 keyword services: discovery, rank tracking, gap analysis, competitor mining, difficulty scoring, and opportunity detection.',
    bg: 'bg-blue-50 dark:bg-blue-950/30',
    iconColor: 'text-blue-600 dark:text-blue-400',
  },
  {
    icon: Target,
    title: 'Niche Radar',
    description: 'Detects emerging micro-niches via keyword, ranking, and feature anomalies. Find underserved markets before your competitors.',
    bg: 'bg-green-50 dark:bg-green-950/30',
    iconColor: 'text-green-600 dark:text-green-400',
  },
  {
    icon: BarChart3,
    title: 'Download & Revenue Estimation',
    description: '4-layer ensemble model using rank curves, review velocity, keyword visibility, and momentum for accurate estimates.',
    bg: 'bg-indigo-50 dark:bg-indigo-950/30',
    iconColor: 'text-indigo-600 dark:text-indigo-400',
  },
  {
    icon: LineChart,
    title: 'Rank Tracking & History',
    description: 'Full chart position history across 21 App Store categories. Track competitors and monitor your own ranking trajectory.',
    bg: 'bg-teal-50 dark:bg-teal-950/30',
    iconColor: 'text-teal-600 dark:text-teal-400',
  },
  {
    icon: Eye,
    title: 'Opportunity Engine',
    description: 'Daily curated opportunities: keyword gaps, app ideas, and emerging niches served with diversity logic so you never miss a trend.',
    bg: 'bg-rose-50 dark:bg-rose-950/30',
    iconColor: 'text-rose-600 dark:text-rose-400',
  },
  {
    icon: Flame,
    title: 'Trending & New Releases',
    description: 'Real-time trending apps with momentum scores and daily new release tracking across all categories.',
    bg: 'bg-orange-50 dark:bg-orange-950/30',
    iconColor: 'text-orange-600 dark:text-orange-400',
  },
];

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: '/forever',
    description: 'Explore the platform basics',
    features: [
      { text: '5 app imports / month', included: true },
      { text: '10 keyword refreshes / month', included: true },
      { text: '5 AI requests / month', included: true },
      { text: 'Export data', included: false },
      { text: 'Premium features', included: false },
    ],
    cta: 'Get Started',
    popular: false,
    color: 'border-gray-200 dark:border-gray-800',
  },
  {
    name: 'Starter',
    price: '$29',
    period: '/month',
    description: 'For indie developers getting started',
    features: [
      { text: '100 app imports / month', included: true },
      { text: '200 keyword refreshes / month', included: true },
      { text: '100 AI requests / month', included: true },
      { text: '50 exports / month', included: true },
      { text: 'All premium features', included: true },
    ],
    cta: 'Start Free Trial',
    popular: false,
    color: 'border-gray-200 dark:border-gray-800',
  },
  {
    name: 'Pro',
    price: '$79',
    period: '/month',
    description: 'For serious ASO professionals',
    features: [
      { text: 'Unlimited app imports', included: true },
      { text: 'Unlimited keyword refreshes', included: true },
      { text: 'Unlimited AI requests', included: true },
      { text: 'Unlimited exports', included: true },
      { text: 'All premium features', included: true },
    ],
    cta: 'Start Free Trial',
    popular: true,
    color: 'border-indigo-500 dark:border-indigo-400',
  },
  {
    name: 'Enterprise',
    price: '$199',
    period: '/month',
    description: 'For teams and agencies',
    features: [
      { text: 'Everything in Pro', included: true },
      { text: 'Priority support', included: true },
      { text: 'Custom integrations', included: true },
      { text: 'Dedicated account manager', included: true },
      { text: 'SLA guarantee', included: true },
    ],
    cta: 'Contact Sales',
    popular: false,
    color: 'border-gray-200 dark:border-gray-800',
  },
];

const STATS = [
  { value: '2M+', label: 'Apps Tracked' },
  { value: '500K+', label: 'Keywords Monitored' },
  { value: '21', label: 'Categories Covered' },
  { value: '24/7', label: 'Real-time Monitoring' },
];

const TESTIMONIALS = [
  {
    quote: "RankSpy's AI idea generator found me a niche nobody was targeting. My app hit #3 in its category within 2 weeks.",
    name: 'Sarah K.',
    role: 'Indie Developer',
    avatar: 'S',
  },
  {
    quote: "We replaced Sensor Tower with RankSpy. The keyword intelligence is on par, the AI insights are unique, and we save $4,000/month.",
    name: 'Marcus T.',
    role: 'ASO Lead at Appify',
    avatar: 'M',
  },
  {
    quote: "The blowing-up detection caught a competitor's growth 10 days before anyone else noticed. That early signal was invaluable.",
    name: 'James L.',
    role: 'Growth PM',
    avatar: 'J',
  },
];

const FAQS = [
  {
    q: 'How does the 7-day free trial work?',
    a: 'Sign up with just your email and password — no credit card required. You get full access to all Pro features for 7 days. If you love it, pick a plan. If not, you can continue on the free tier.',
  },
  {
    q: 'What makes RankSpy different from Sensor Tower or data.ai?',
    a: "We're the first ASO tool with AI-powered intelligence. While others give you raw data, we generate actionable app ideas, detect niches automatically, and analyze reviews with LLM intelligence. Plus, we're 10-50x more affordable.",
  },
  {
    q: 'How accurate are the download and revenue estimates?',
    a: 'Our 4-layer ensemble model combines rank curves, review velocity, keyword visibility, and momentum signals. While no estimate is perfect, our model is continuously calibrated against real-world data.',
  },
  {
    q: 'Can I track my competitors\' apps?',
    a: 'Absolutely. Add any app to your tracked list and monitor rank changes, review sentiment, keyword positions, and growth signals in real-time.',
  },
  {
    q: 'Do you support the Google Play Store?',
    a: 'Currently we focus exclusively on the iOS App Store. Google Play support is on our roadmap for the future.',
  },
  {
    q: 'Can I cancel my subscription anytime?',
    a: 'Yes. You can cancel anytime from your account settings. No long-term contracts, no cancellation fees. Your data stays accessible on the free tier.',
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
  { feature: 'Starting Price', us: '$0/mo', others: '$149/mo' },
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
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? 'bg-white/80 dark:bg-gray-950/80 backdrop-blur-xl border-b border-gray-200/50 dark:border-gray-800/50 shadow-sm'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md shadow-indigo-500/20">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </div>

          <div className="hidden md:flex items-center gap-8">
            {['Features', 'Pricing', 'Compare', 'FAQ'].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase()}`}
                className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors duration-200"
              >
                {item}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white px-4 py-2 rounded-lg transition-colors duration-200"
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg transition-all duration-200 shadow-sm shadow-indigo-500/25 hover:shadow-md hover:shadow-indigo-500/30 hover:-translate-y-px"
            >
              Start Free Trial
            </Link>
          </div>

          <button onClick={() => setMobileOpen(!mobileOpen)} className="md:hidden p-2 text-gray-600 dark:text-gray-400">
            <Menu className="w-5 h-5" />
          </button>
        </div>

        {mobileOpen && (
          <div className="md:hidden pb-4 border-t border-gray-200/50 dark:border-gray-800/50 mt-2 pt-4 space-y-3 animate-[slideDown_0.2s_ease-out]">
            {['Features', 'Pricing', 'Compare', 'FAQ'].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`} onClick={() => setMobileOpen(false)} className="block text-sm text-gray-600 dark:text-gray-400 py-1.5">
                {item}
              </a>
            ))}
            <div className="flex gap-3 pt-2">
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
    <section className="relative pt-32 pb-20 sm:pt-40 sm:pb-28 overflow-hidden">
      {/* Animated background blobs */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-indigo-100/60 via-purple-50/40 to-transparent dark:from-indigo-950/40 dark:via-purple-950/20 rounded-full blur-3xl animate-[pulse_8s_ease-in-out_infinite]" />
        <div className="absolute top-20 right-0 w-[400px] h-[400px] bg-gradient-to-bl from-cyan-100/40 to-transparent dark:from-cyan-950/20 rounded-full blur-3xl animate-[pulse_6s_ease-in-out_infinite_1s]" />
        <div className="absolute top-40 left-0 w-[300px] h-[300px] bg-gradient-to-br from-pink-100/30 to-transparent dark:from-pink-950/15 rounded-full blur-3xl animate-[pulse_7s_ease-in-out_infinite_2s]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(30px)',
            transition: 'opacity 0.8s cubic-bezier(0.16,1,0.3,1) 0.1s, transform 0.8s cubic-bezier(0.16,1,0.3,1) 0.1s',
          }}
        >
          <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight text-gray-900 dark:text-white leading-[1.08] max-w-4xl mx-auto">
            Discover Your Next{' '}
            <span className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 bg-clip-text text-transparent animate-[gradientShift_6s_ease_infinite] bg-[length:200%_auto]">
              App Store Opportunity
            </span>
          </h1>
        </div>

        <div
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(30px)',
            transition: 'opacity 0.8s cubic-bezier(0.16,1,0.3,1) 0.3s, transform 0.8s cubic-bezier(0.16,1,0.3,1) 0.3s',
          }}
        >
          <p className="mt-6 text-lg sm:text-xl text-gray-600 dark:text-gray-400 max-w-2xl mx-auto leading-relaxed">
            AI-powered market intelligence that finds winning app ideas, tracks competitors, and surfaces keyword opportunities — before anyone else.
          </p>
        </div>

        <div
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(30px)',
            transition: 'opacity 0.8s cubic-bezier(0.16,1,0.3,1) 0.5s, transform 0.8s cubic-bezier(0.16,1,0.3,1) 0.5s',
          }}
        >
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/signup"
              className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-8 py-3.5 rounded-xl text-base transition-all duration-300 shadow-lg shadow-indigo-500/25 hover:shadow-xl hover:shadow-indigo-500/40 hover:-translate-y-0.5"
            >
              Start Free Trial
              <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
            <a
              href="#features"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 font-medium px-8 py-3.5 rounded-xl text-base border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-all duration-300 hover:-translate-y-0.5"
            >
              See How It Works
              <ChevronDown className="w-4 h-4 animate-bounce" />
            </a>
          </div>

          <p className="mt-5 text-sm text-gray-500 dark:text-gray-500">
            7-day free trial &middot; No credit card required &middot; Cancel anytime
          </p>
        </div>

        {/* Animated Stats */}
        <div className="mt-16 grid grid-cols-2 gap-4 sm:grid-cols-4 max-w-3xl mx-auto">
          {STATS.map((s, i) => (
            <AnimateIn key={s.label} from="bottom" delay={0.6 + i * 0.1}>
              <div className="rounded-xl bg-white/60 dark:bg-gray-900/60 backdrop-blur-sm border border-gray-200/60 dark:border-gray-800/60 px-4 py-4 hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
                <p className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
                  <AnimatedCounter value={s.value} />
                </p>
                <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mt-0.5">{s.label}</p>
              </div>
            </AnimateIn>
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Features</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Everything You Need to Win the App Store
          </h2>
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">
            From idea generation to rank tracking, our AI-powered platform covers every step of your ASO journey.
          </p>
        </AnimateIn>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <AnimateIn key={f.title} delay={i * 0.08} from={i % 3 === 0 ? 'left' : i % 3 === 2 ? 'right' : 'bottom'}>
              <div className="group rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 hover:border-indigo-200 dark:hover:border-indigo-800 hover:shadow-xl hover:shadow-indigo-500/5 transition-all duration-500 hover:-translate-y-1">
                <div className={`w-11 h-11 rounded-xl ${f.bg} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-500`}>
                  <f.icon className={`w-5 h-5 ${f.iconColor}`} />
                </div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2">{f.title}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{f.description}</p>
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
    { num: '04', title: 'Build & Grow', desc: 'Use AI-generated insights to build apps that users actually want, optimized for discovery from day one.', icon: TrendingUp },
  ];

  return (
    <section className="py-20 sm:py-28 bg-gray-50/50 dark:bg-gray-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">How It Works</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            From Data to App Ideas in Minutes
          </h2>
        </AnimateIn>

        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <AnimateIn key={s.num} delay={i * 0.15} from="bottom">
              <div className="relative text-center group">
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-10 left-[60%] w-[80%] h-px bg-gradient-to-r from-indigo-300 to-transparent dark:from-indigo-700" />
                )}
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-sm mb-5 group-hover:shadow-lg group-hover:border-indigo-200 dark:group-hover:border-indigo-800 group-hover:-translate-y-2 transition-all duration-500">
                  <s.icon className="w-8 h-8 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform duration-500" />
                </div>
                <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400 mb-2">{s.num}</div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2">{s.title}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{s.desc}</p>
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
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-12">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Compare</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Why Teams Switch to RankSpy
          </h2>
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">
            More features, AI-powered intelligence, and 10-50x more affordable.
          </p>
        </AnimateIn>

        <div ref={ref} className="rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-900/60">
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Feature</th>
                <th className="px-6 py-4 text-center text-sm font-semibold text-indigo-600 dark:text-indigo-400">
                  <div className="flex items-center justify-center gap-1.5">
                    <Zap className="w-4 h-4" /> RankSpy
                  </div>
                </th>
                <th className="px-6 py-4 text-center text-sm font-semibold text-gray-500 dark:text-gray-400">Others</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {COMPARISONS.map((row, i) => (
                <tr
                  key={row.feature}
                  className="bg-white dark:bg-gray-950"
                  style={{
                    opacity: visible ? 1 : 0,
                    transform: visible ? 'translateX(0)' : 'translateX(-20px)',
                    transition: `opacity 0.5s ease ${i * 0.07}s, transform 0.5s ease ${i * 0.07}s`,
                  }}
                >
                  <td className="px-6 py-3.5 text-sm text-gray-700 dark:text-gray-300">{row.feature}</td>
                  <td className="px-6 py-3.5 text-center">
                    {typeof row.us === 'boolean' ? (
                      row.us ? <Check className="w-5 h-5 text-green-500 mx-auto" /> : <X className="w-5 h-5 text-red-400 mx-auto" />
                    ) : (
                      <span className="text-sm font-semibold text-green-600 dark:text-green-400">{row.us}</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 text-center">
                    {typeof row.others === 'boolean' ? (
                      row.others ? <Check className="w-5 h-5 text-green-500 mx-auto" /> : <X className="w-5 h-5 text-red-400 mx-auto" />
                    ) : (
                      <span className="text-sm font-semibold text-red-500">{row.others}</span>
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
// Pricing
// ---------------------------------------------------------------------------

function PricingSection() {
  return (
    <section id="pricing" className="py-20 sm:py-28 bg-gray-50/50 dark:bg-gray-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Pricing</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Simple, Transparent Pricing
          </h2>
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">
            Start free, upgrade when you&apos;re ready. No hidden fees, no surprises.
          </p>
        </AnimateIn>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 max-w-6xl mx-auto">
          {PLANS.map((plan, i) => (
            <AnimateIn key={plan.name} delay={i * 0.12} from="scale">
              <div
                className={`relative rounded-2xl border-2 ${plan.color} bg-white dark:bg-gray-900 p-6 flex flex-col h-full hover:-translate-y-2 transition-all duration-500 ${
                  plan.popular ? 'ring-1 ring-indigo-500/20 shadow-xl shadow-indigo-500/10 hover:shadow-2xl hover:shadow-indigo-500/20' : 'hover:shadow-lg'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 inline-flex items-center gap-1.5 bg-indigo-600 text-white text-xs font-semibold px-3 py-1 rounded-full animate-pulse">
                    <Crown className="w-3 h-3" /> Most Popular
                  </div>
                )}
                <div className="mb-5">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{plan.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{plan.description}</p>
                </div>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-4xl font-bold text-gray-900 dark:text-white">{plan.price}</span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">{plan.period}</span>
                </div>
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <li key={f.text} className="flex items-start gap-2.5">
                      {f.included ? (
                        <Check className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                      ) : (
                        <X className="w-4 h-4 text-gray-300 dark:text-gray-600 mt-0.5 flex-shrink-0" />
                      )}
                      <span className={`text-sm ${f.included ? 'text-gray-700 dark:text-gray-300' : 'text-gray-400 dark:text-gray-600'}`}>
                        {f.text}
                      </span>
                    </li>
                  ))}
                </ul>
                <Link
                  href="/signup"
                  className={`w-full text-center py-2.5 rounded-lg text-sm font-semibold transition-all duration-300 hover:-translate-y-px ${
                    plan.popular
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-500/25 hover:shadow-md hover:shadow-indigo-500/40'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            </AnimateIn>
          ))}
        </div>

        <AnimateIn className="text-center mt-8">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            All plans include a 7-day free trial. No credit card required.
          </p>
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Testimonials</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Loved by Developers & Growth Teams
          </h2>
        </AnimateIn>

        <div className="grid gap-6 md:grid-cols-3">
          {TESTIMONIALS.map((t, i) => (
            <AnimateIn key={t.name} delay={i * 0.15} from={i === 0 ? 'left' : i === 2 ? 'right' : 'bottom'}>
              <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 hover:shadow-lg hover:-translate-y-1 transition-all duration-500">
                <div className="flex gap-1 mb-4">
                  {[...Array(5)].map((_, j) => (
                    <Star key={j} className="w-4 h-4 text-amber-400 fill-amber-400" />
                  ))}
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed mb-5">&ldquo;{t.quote}&rdquo;</p>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-sm font-bold">
                    {t.avatar}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{t.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{t.role}</p>
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
    <section id="faq" className="py-20 sm:py-28 bg-gray-50/50 dark:bg-gray-900/30">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateIn className="text-center mb-12">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">FAQ</span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
            Frequently Asked Questions
          </h2>
        </AnimateIn>

        <div className="space-y-3">
          {FAQS.map((faq, i) => (
            <AnimateIn key={i} delay={i * 0.08} from="bottom">
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden hover:border-indigo-200 dark:hover:border-indigo-800 transition-colors duration-300">
                <button
                  onClick={() => setOpenIndex(openIndex === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                >
                  <span className="text-sm font-medium text-gray-900 dark:text-white pr-4">{faq.q}</span>
                  <ChevronDown
                    className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform duration-300 ${openIndex === i ? 'rotate-180' : ''}`}
                  />
                </button>
                <div
                  className="overflow-hidden transition-all duration-300"
                  style={{
                    maxHeight: openIndex === i ? '200px' : '0',
                    opacity: openIndex === i ? 1 : 0,
                  }}
                >
                  <div className="px-5 pb-4">
                    <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{faq.a}</p>
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
          <div className="rounded-3xl bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 p-10 sm:p-16 relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(255,255,255,0.1),transparent_60%)]" />
            {/* Floating particles */}
            <div className="absolute top-8 left-8 w-3 h-3 rounded-full bg-white/20 animate-[float_4s_ease-in-out_infinite]" />
            <div className="absolute top-16 right-16 w-2 h-2 rounded-full bg-white/15 animate-[float_5s_ease-in-out_infinite_1s]" />
            <div className="absolute bottom-12 left-1/4 w-2.5 h-2.5 rounded-full bg-white/10 animate-[float_6s_ease-in-out_infinite_2s]" />
            <div className="relative">
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                Ready to Find Your Next Big App?
              </h2>
              <p className="text-lg text-indigo-100 mb-8 max-w-xl mx-auto">
                Join thousands of developers using AI to discover App Store opportunities before the competition.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/signup"
                  className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-white text-indigo-700 font-semibold px-8 py-3.5 rounded-xl text-base hover:bg-indigo-50 transition-all duration-300 shadow-lg hover:-translate-y-0.5"
                >
                  Start Free Trial
                  <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
                </Link>
                <Link
                  href="/login"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-white/10 text-white font-medium px-8 py-3.5 rounded-xl text-base border border-white/20 hover:bg-white/20 transition-all duration-300"
                >
                  Sign In
                </Link>
              </div>
              <p className="mt-5 text-sm text-indigo-200">
                No credit card required &middot; 7-day free trial &middot; Cancel anytime
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
    <footer className="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md shadow-indigo-500/20">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed max-w-sm mb-5">
              AI-powered App Store intelligence platform. Discover opportunities, track competitors, and build winning apps.
            </p>
            <div className="flex items-center gap-3">
              {[Twitter, Github, Linkedin].map((Icon, i) => (
                <a
                  key={i}
                  href="#"
                  className="w-9 h-9 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 hover:-translate-y-0.5 transition-all duration-300"
                >
                  <Icon className="w-4 h-4" />
                </a>
              ))}
            </div>
          </div>

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
              title: 'Support',
              links: [
                { label: 'Contact Us', href: 'mailto:support@rankspy.app' },
                { label: 'Help Center', href: 'mailto:support@rankspy.app' },
                { label: 'Feature Requests', href: 'mailto:support@rankspy.app' },
                { label: 'Bug Reports', href: 'mailto:support@rankspy.app' },
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
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">{section.title}</h4>
              <ul className="space-y-2.5">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <a href={link.href} className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-200">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 pt-8 border-t border-gray-200 dark:border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-sm text-gray-500 dark:text-gray-500">
            &copy; {new Date().getFullYear()} RankSpy. All rights reserved.
          </p>
          <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-500">
            <a href="mailto:support@rankspy.app" className="hover:text-gray-700 dark:hover:text-gray-300 transition-colors">support@rankspy.app</a>
          </div>
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
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      {/* Global keyframes */}
      <style jsx global>{`
        @keyframes gradientShift {
          0%, 100% { background-position: 0% center; }
          50% { background-position: 100% center; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-12px); }
        }
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <Navbar />
      <HeroSection />
      <FeaturesSection />
      <HowItWorksSection />
      <CompareSection />
      <TestimonialsSection />
      <PricingSection />
      <FAQSection />
      <CTASection />
      <Footer />
    </div>
  );
}
