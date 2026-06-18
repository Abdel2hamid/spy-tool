'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetJobs,
  adminTriggerJob,
  AdminJobItem,
} from '@/lib/api';
import { Play, RefreshCw } from 'lucide-react';

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJobItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminGetJobs()
      .then((d) => setJobs(d.jobs))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

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
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Scheduler Jobs</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{jobs.length} scheduled jobs</p>
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
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Job ID</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Trigger</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Next Run</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-12 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
              ) : jobs.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-12 text-center text-gray-400">No jobs found</td></tr>
              ) : jobs.map((j) => (
                <tr key={j.job_id} className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition">
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs font-medium text-gray-900 dark:text-white">{j.job_id}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-[300px]">
                    <span className="block truncate">{j.trigger || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                    {j.next_run ? new Date(j.next_run).toLocaleString() : '—'}
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
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AdminShell>
  );
}
