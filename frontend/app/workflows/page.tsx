"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export default function WorkflowsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns();
    // Poll for updates every 3 seconds
    const interval = setInterval(fetchRuns, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchRuns = async () => {
    try {
      const response = await fetch(`${API_URL}/api/runs?limit=20`);
      if (!response.ok) throw new Error("Failed to fetch runs");
      const data = await response.json();
      setRuns(data);
      setLoading(false);
    } catch (err) {
      console.error("Error fetching runs:", err);
      if (loading) {
        setError(err instanceof Error ? err.message : "Failed to fetch runs");
        setLoading(false);
      }
    }
  };

  const triggerRSSWorkflow = async () => {
    try {
      setTriggering(true);
      setError(null);
      setSuccess(null);

      const response = await fetch(`${API_URL}/api/workflows/rss/trigger`, {
        method: "POST",
      });

      if (!response.ok) throw new Error("Failed to trigger RSS workflow");

      const data = await response.json();
      setSuccess(`RSS workflow started with run_id: ${data.run_id}`);

      // Refresh runs immediately
      fetchRuns();

      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger RSS workflow");
    } finally {
      setTriggering(false);
    }
  };

  const toggleExpanded = (runId: string) => {
    const newExpanded = new Set(expandedRuns);
    if (newExpanded.has(runId)) {
      newExpanded.delete(runId);
    } else {
      newExpanded.add(runId);
    }
    setExpandedRuns(newExpanded);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex justify-center items-center h-screen">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Workflows</h1>
        <button
          onClick={triggerRSSWorkflow}
          disabled={triggering}
          className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {triggering ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Running...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Run RSS Workflow
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded shadow-sm">
          <div className="flex items-center">
            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        </div>
      )}

      {success && (
        <div className="mb-4 bg-green-50 border-l-4 border-green-500 text-green-700 px-4 py-3 rounded shadow-sm">
          <div className="flex items-center">
            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            {success}
          </div>
        </div>
      )}

      <div className="bg-white shadow-md rounded-lg overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">RSS Parsing Runs</h2>
          <p className="text-sm text-gray-500 mt-1">Recent workflow executions</p>
        </div>

        {runs.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            No runs yet. Click "Run RSS Workflow" to start.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {runs.map((run) => (
              <div key={run.run_id} className="hover:bg-gray-50 transition-colors">
                <div
                  className="px-6 py-4 cursor-pointer"
                  onClick={() => toggleExpanded(run.run_id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4 flex-1">
                      <div className="flex-shrink-0">
                        <svg
                          className={`w-5 h-5 transition-transform ${
                            expandedRuns.has(run.run_id) ? "rotate-90" : ""
                          }`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-mono text-gray-900 truncate">
                          {run.run_id}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Started: {formatDate(run.started_at)}
                        </p>
                      </div>
                      <div className="flex items-center space-x-3">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                            run.status
                          )}`}
                        >
                          {run.status}
                        </span>
                        {run.status === "completed" && (
                          <div className="text-xs text-gray-600">
                            <span className="font-medium">{run.items_inserted}</span> /{" "}
                            <span>{run.items_extracted}</span> items
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {expandedRuns.has(run.run_id) && (
                  <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="font-medium text-gray-700">Run ID:</span>
                        <p className="text-gray-900 font-mono text-xs mt-1">{run.run_id}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Status:</span>
                        <p className="text-gray-900 mt-1">{run.status}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Started At:</span>
                        <p className="text-gray-900 mt-1">{formatDate(run.started_at)}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Completed At:</span>
                        <p className="text-gray-900 mt-1">{formatDate(run.completed_at)}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Sources Processed:</span>
                        <p className="text-gray-900 mt-1">{run.sources_processed}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Items Extracted:</span>
                        <p className="text-gray-900 mt-1">{run.items_extracted}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Items Inserted:</span>
                        <p className="text-gray-900 mt-1">{run.items_inserted}</p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Duplicate Rate:</span>
                        <p className="text-gray-900 mt-1">
                          {run.items_extracted > 0
                            ? `${(
                                ((run.items_extracted - run.items_inserted) /
                                  run.items_extracted) *
                                100
                              ).toFixed(1)}%`
                            : "N/A"}
                        </p>
                      </div>
                      {run.error_message && (
                        <div className="col-span-2">
                          <span className="font-medium text-red-700">Error:</span>
                          <p className="text-red-900 mt-1 bg-red-50 p-2 rounded font-mono text-xs">
                            {run.error_message}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
