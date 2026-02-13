"use client";

import { useEffect, useState } from "react";
import type { DataSource } from "@/types/database";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DataSourcesPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [originalDataSources, setOriginalDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchDataSources();
  }, []);

  const fetchDataSources = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/datasources`);

      if (!response.ok) throw new Error("Failed to fetch data sources");

      const data = await response.json();
      setDataSources(data || []);
      setOriginalDataSources(data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data sources");
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = (sourceId: number) => {
    setDataSources((prev) =>
      prev.map((source) =>
        source.id === sourceId
          ? { ...source, active: source.active === "true" ? "false" : "true" }
          : source
      )
    );
  };

  const hasChanges = () => {
    return dataSources.some((source, index) =>
      source.active !== originalDataSources[index]?.active
    );
  };

  const saveChanges = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      // Find all changed sources
      const changedSources = dataSources.filter((source, index) =>
        source.active !== originalDataSources[index]?.active
      );

      // Update each changed source
      await Promise.all(
        changedSources.map((source) =>
          fetch(`${API_URL}/api/datasources/${source.id}`, {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ active: source.active }),
          })
        )
      );

      setSuccess(`Successfully updated ${changedSources.length} data source(s)`);
      setOriginalDataSources(dataSources);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  const cancelChanges = () => {
    setDataSources(originalDataSources);
    setError(null);
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
        <h1 className="text-3xl font-bold text-gray-900">Data Sources</h1>
        {hasChanges() && (
          <div className="flex gap-3">
            <button
              onClick={cancelChanges}
              disabled={saving}
              className="px-5 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={saveChanges}
              disabled={saving}
              className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving ? (
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
                  Saving...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Save Changes
                </>
              )}
            </button>
          </div>
        )}
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
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                URL
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Active
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {dataSources.map((source) => (
              <tr key={source.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {source.id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {source.name}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 max-w-md truncate">
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800"
                  >
                    {source.url}
                  </a>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <button
                    onClick={() => toggleActive(source.id)}
                    className={`group relative inline-flex h-7 w-14 items-center rounded-full transition-all duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 shadow-sm ${
                      source.active === "true"
                        ? "bg-gradient-to-r from-emerald-500 to-emerald-600 focus:ring-emerald-500"
                        : "bg-gray-300 hover:bg-gray-400 focus:ring-gray-400"
                    }`}
                    role="switch"
                    aria-checked={source.active === "true"}
                    title={source.active === "true" ? "Click to deactivate" : "Click to activate"}
                  >
                    <span
                      className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-all duration-300 ease-in-out group-hover:scale-105 ${
                        source.active === "true" ? "translate-x-8" : "translate-x-1"
                      }`}
                    />
                    {/* Status indicator dot */}
                    <span
                      className={`absolute transition-opacity duration-300 ${
                        source.active === "true"
                          ? "left-2 opacity-100"
                          : "right-2 opacity-50"
                      }`}
                    >
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${
                          source.active === "true" ? "bg-white" : "bg-gray-600"
                        }`}
                      />
                    </span>
                  </button>
                  <span
                    className={`ml-3 text-xs font-medium ${
                      source.active === "true" ? "text-emerald-600" : "text-gray-500"
                    }`}
                  >
                    {source.active === "true" ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}
