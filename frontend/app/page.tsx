'use client';

import { useEffect, useState } from 'react';

interface DataSource {
  id: number;
  name: string;
  type: string;
  url: string;
  active: string;
}

interface Run {
  run_id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  sources_processed: number;
  items_extracted: number;
  items_inserted: number;
  error_message: string | null;
}

export default function Home() {
  const [activeSources, setActiveSources] = useState<DataSource[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sourcesResponse, runsResponse] = await Promise.all([
          fetch('http://localhost:8000/api/datasources'),
          fetch('http://localhost:8000/api/runs'),
        ]);

        const sources: DataSource[] = await sourcesResponse.json();
        const runsData: Run[] = await runsResponse.json();

        setActiveSources(sources.filter(ds => ds.active === 'true'));
        setRuns(runsData);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const toggleExpand = (runId: string) => {
    setExpandedRunId(expandedRunId === runId ? null : runId);
  };

  const calculateInsertionRate = (extracted: number, inserted: number) => {
    if (extracted === 0) return 0;
    return ((inserted / extracted) * 100).toFixed(1);
  };

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-4">
        Threat Intelligence Dashboard
      </h1>
      <p className="text-gray-600 mb-8">
        Welcome to your threat intelligence management system. Use the sidebar to navigate to different sections.
      </p>

      {/* Active Sources Card */}
      <div className="mb-8">
        <div className="bg-white overflow-hidden shadow rounded-lg max-w-xs">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Active Sources
                  </dt>
                  <dd className="mt-1 text-3xl font-semibold text-gray-900">
                    {loading ? '--' : activeSources.length}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Runs Table */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Recent Runs
        </h2>
        <div className="bg-white shadow overflow-hidden rounded-lg">
          <div className="overflow-x-auto">
            {loading ? (
              <div className="p-6 text-center text-gray-500">Loading runs...</div>
            ) : runs.length > 0 ? (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">

                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Run ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Started At
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Sources
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Extracted
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Inserted
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {runs.map((run) => (
                    <>
                      <tr
                        key={run.run_id}
                        onClick={() => toggleExpand(run.run_id)}
                        className="hover:bg-gray-50 cursor-pointer"
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <svg
                            className={`w-5 h-5 transform transition-transform ${expandedRunId === run.run_id ? 'rotate-90' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs">
                          <code className="bg-gray-100 px-2 py-1 rounded text-gray-900 font-mono">
                            {run.run_id}
                          </code>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDate(run.started_at)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(run.status)}`}>
                            {run.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {run.sources_processed}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {run.items_extracted}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {run.items_inserted}
                        </td>
                      </tr>
                      {expandedRunId === run.run_id && (
                        <tr key={`${run.run_id}-details`}>
                          <td colSpan={7} className="px-6 py-4 bg-gray-50">
                            <div className="space-y-3">
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Run Details</h4>
                                  <dl className="space-y-1">
                                    <div className="flex justify-between">
                                      <dt className="text-xs text-gray-500">Full Run ID:</dt>
                                      <dd className="text-xs font-mono text-gray-900">{run.run_id}</dd>
                                    </div>
                                    <div className="flex justify-between">
                                      <dt className="text-xs text-gray-500">Started:</dt>
                                      <dd className="text-xs text-gray-900">{formatDate(run.started_at)}</dd>
                                    </div>
                                    <div className="flex justify-between">
                                      <dt className="text-xs text-gray-500">Completed:</dt>
                                      <dd className="text-xs text-gray-900">
                                        {run.completed_at ? formatDate(run.completed_at) : 'N/A'}
                                      </dd>
                                    </div>
                                  </dl>
                                </div>
                                <div>
                                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Metrics</h4>
                                  <dl className="space-y-1">
                                    <div className="flex justify-between">
                                      <dt className="text-xs text-gray-500">Insertion Rate:</dt>
                                      <dd className="text-xs text-gray-900">
                                        {calculateInsertionRate(run.items_extracted, run.items_inserted)}%
                                      </dd>
                                    </div>
                                    <div className="flex justify-between">
                                      <dt className="text-xs text-gray-500">Duplicates Filtered:</dt>
                                      <dd className="text-xs text-gray-900">
                                        {run.items_extracted - run.items_inserted}
                                      </dd>
                                    </div>
                                  </dl>
                                </div>
                              </div>
                              {run.error_message && (
                                <div>
                                  <h4 className="text-sm font-semibold text-red-700 mb-1">Error Message</h4>
                                  <p className="text-xs text-red-600 bg-red-50 p-2 rounded">
                                    {run.error_message}
                                  </p>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-6 text-center text-gray-500">No runs found</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
