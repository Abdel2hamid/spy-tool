'use client';

import { Component, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error) {
    console.error('[ErrorBoundary]', error);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-red-200 bg-red-50 p-8 text-center dark:border-red-900 dark:bg-red-950/30">
          <AlertTriangle className="mb-4 h-10 w-10 text-red-400" />
          <p className="font-semibold text-red-700 dark:text-red-400">
            Something went wrong loading this section
          </p>
          {this.state.error?.message && (
            <p className="mt-2 max-w-md text-sm text-red-500 dark:text-red-500">
              {this.state.error.message}
            </p>
          )}
          <button
            onClick={() => this.setState({ hasError: false })}
            className="mt-6 rounded-lg bg-red-100 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-200 dark:bg-red-900/50 dark:text-red-300 dark:hover:bg-red-900"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
