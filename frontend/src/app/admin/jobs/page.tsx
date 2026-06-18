'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetJobs,
  adminTriggerJob,
  adminGetJobMetrics,
  AdminJobItem,
} from '@/lib/api';
import {
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  Timer,
  Activity,
} from 'lucide-react';

interface JobMetricData {
  runs?: number;
  ok?: number;
  fail?: number;
  timeout?: number;
  last_duration_s?: number;
  [key: string]: unknown;
}

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJobItem[]>([]);
  const [metrics, setMetrics] = useState<Record<string, JobMetricData>>({});
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([adminGetJobs(), adminGetJobMetrics()])
      .then(([jobsData, metricsData]) => {
        setJobs(jobsData.jobs);
        setMetrics(metricsData.metrics as Record<string, JobMetricData>);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleTrigger(jobId: string) {
    setTriggering(jobId);
    try {
      await adminTriggerJob(jobId);
      load();
    } catch {
      // ignore
    } finally {
      setTriggering(null);
    }
  }

  return (
    <AdminShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Scheduler Jobs
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {jobs.length} scheduled jobs
            </p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>

        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left dark:bg-gray-800/50">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Job ID
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Trigger
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Next Run
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Metrics
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Last Duration
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {loading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-12 text-center text-gray-400"
                  >
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto" />
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-12 text-center text-gray-400"
                  >
                    No jobs found
                  </td>
                </tr>
              ) : (
                jobs.map((j) => {
                  const m: JobMetricData = metrics[j.job_id] || {};
                  const runs = Number(m.runs ?? 0);
                  const ok = Number(m.ok ?? 0);
                  const fail = Number(m.fail ?? 0);
                  const timeout = Number(m.timeout ?? 0);
                  const lastDuration = m.last_duration_s;
                  const hasMetrics = runs > 0;

                  return (
                    <tr
                      key={j.job_id}
                      className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition"
                    >
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs font-medium text-gray-900 dark:text-white">
                          {j.job_id}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-[300px]">
                        <span className="block truncate">
                          {j.trigger || '\u2014'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                        {j.next_run
                          ? new Date(j.next_run).toLocaleString()
                          : '\u2014'}
                      </td>
                      <td className="px-4 py-3">
                        {hasMetrics ? (
                          <div className="flex items-center gap-3">
                            <span
                              className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"
                              title="Total runs"
                            >
                              <Activity className="h-3 w-3" />
                              {runs}
                            </span>
                            <span
                              className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400"
                              title="Successful"
                            >
                              <CheckCircle className="h-3 w-3" />
                              {ok}
                            </span>
                            <span
                              className={`flex items-center gap-1 text-xs ${
                                fail > 0
                                  ? 'text-red-600 dark:text-red-400 font-semibold'
                                  : 'text-gray-400'
                              }`}
                              title="Failed"
                            >
                              <XCircle className="h-3 w-3" />
                              {fail}
                            </span>
                            <span
                              className={`flex items-center gap-1 text-xs ${
                                timeout > 0
                                  ? 'text-red-600 dark:text-red-400 font-semibold'
                                  : 'text-gray-400'
                              }`}
                              title="Timed out"
                            >
                              <Timer className="h-3 w-3" />
                              {timeout}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">
                            No data
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {lastDuration !== undefined &&
                        lastDuration !== null ? (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                            {Number(lastDuration).toFixed(1)}s
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">
                            \u2014
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleTrigger(j.job_id)}
                          disabled={triggering === j.job_id}
                          className="flex items-center gap-1.5 rounded-lg bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 disabled:opacity-50 dark:bg-green-950 dark:text-green-400 dark:hover:bg-green-900 transition"
                        >
                          {triggering === j.job_id ? (
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                          Run Now
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AdminShell>
  );
}
