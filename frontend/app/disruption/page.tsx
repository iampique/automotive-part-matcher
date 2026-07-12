'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Loader2,
  AlertTriangle,
  Zap,
  CheckCircle2,
  Search,
} from 'lucide-react';
import { analyzeDisruption, getHealth } from '@/lib/api';
import type { DisruptionResponse, MitigationCandidate } from '@/lib/types';

const HERO_PART = 'EC-2024-3441';

function verdictBadge(verdict: MitigationCandidate['verdict']) {
  if (verdict === 'preferred') return 'bg-green-100 text-green-800 border-green-200';
  if (verdict === 'caution') return 'bg-amber-100 text-amber-800 border-amber-200';
  return 'bg-red-100 text-red-800 border-red-200';
}

export default function DisruptionPage() {
  const [partNumber, setPartNumber] = useState(HERO_PART);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DisruptionResponse | null>(null);

  async function handleAnalyze(pn?: string) {
    const target = (pn ?? partNumber).trim();
    if (!target) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await analyzeDisruption({
        part_number: target,
        max_alternatives: 8,
        min_similarity: 55,
      });
      setResult(data);
      const health = await getHealth();
      if (health.neo4j !== 'connected') {
        setError(
          'Neo4j disconnected — graph steps were skipped. Update Aura in backend/.env, run ingest_graph.py, restart backend for the full demo.'
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-purple-50 to-indigo-50">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-purple-700 hover:text-purple-900 font-medium mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Search
        </Link>

        <div className="flex items-center gap-3 mb-2">
          <Zap className="w-9 h-9 text-purple-600" />
          <h1 className="text-3xl font-bold text-gray-900">Disruption Mitigation</h1>
        </div>
        <p className="text-gray-600 mb-8 max-w-2xl">
          Orchestrated workflow: Neo4j impact → Qdrant alternatives → compliance subgraphs →
          supplier topology → ranked substitutes.
        </p>

        <div className="bg-white rounded-2xl shadow-lg border p-6 mb-8">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Disrupted part number
          </label>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={partNumber}
              onChange={(e) => setPartNumber(e.target.value)}
              className="flex-1 border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              placeholder="e.g. EC-2024-3441"
            />
            <button
              onClick={() => handleAnalyze()}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-60 text-white font-semibold px-6 py-3 rounded-xl"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              Analyze Disruption
            </button>
          </div>
          <button
            onClick={() => {
              setPartNumber(HERO_PART);
              handleAnalyze(HERO_PART);
            }}
            className="mt-3 text-sm text-purple-700 hover:text-purple-900 font-medium"
          >
            Load demo part: {HERO_PART} (11-pin BMS / Infotainment)
          </button>
        </div>

        {error && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 mb-6">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
            <p className="text-amber-900">{error}</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center py-16">
            <Loader2 className="w-12 h-12 animate-spin text-purple-600 mb-4" />
            <p className="text-gray-600 font-medium">Running disruption workflow...</p>
          </div>
        )}

        {result && !loading && (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-2xl p-6 shadow-lg">
              <p className="text-sm opacity-90 mb-1">Summary</p>
              <p className="text-xl font-semibold leading-relaxed">{result.summary}</p>
            </div>

            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-white rounded-xl border p-4 shadow-sm">
                <p className="text-xs font-semibold text-red-600 uppercase">Vehicles Affected</p>
                <p className="text-3xl font-bold text-gray-900">{result.impact.affected_vehicles.length}</p>
              </div>
              <div className="bg-white rounded-xl border p-4 shadow-sm">
                <p className="text-xs font-semibold text-orange-600 uppercase">Critical Paths</p>
                <p className="text-3xl font-bold text-gray-900">{result.impact.critical_paths.length}</p>
              </div>
              <div className="bg-white rounded-xl border p-4 shadow-sm">
                <p className="text-xs font-semibold text-green-600 uppercase">Alternatives</p>
                <p className="text-3xl font-bold text-gray-900">{result.alternatives.length}</p>
              </div>
            </div>

            <section className="bg-white rounded-2xl border shadow-sm p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Execution Trace</h2>
              <div className="space-y-2">
                {result.execution_trace.map((step) => (
                  <div
                    key={step.node}
                    className="flex items-center justify-between text-sm border rounded-lg px-4 py-2 bg-gray-50"
                  >
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                      <span className="font-medium capitalize">{step.node.replace(/_/g, ' ')}</span>
                      <span className="text-gray-500">— {step.output}</span>
                    </div>
                    <span className="text-gray-400 text-xs">{step.duration_ms.toFixed(0)}ms</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-white rounded-2xl border shadow-sm p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Ranked Mitigation Options</h2>
              <div className="space-y-3">
                {result.alternatives.map((alt, index) => (
                  <div key={alt.part_number} className="border rounded-xl p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-purple-600">#{index + 1}</span>
                        <div>
                          <p className="font-bold">{alt.part_number}</p>
                          <p className="text-sm text-gray-600">{alt.name}</p>
                        </div>
                      </div>
                      <span className={`text-xs font-bold px-3 py-1 rounded-full border ${verdictBadge(alt.verdict)}`}>
                        {alt.verdict.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mb-2">{alt.recommendation}</p>
                    <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                      <span>Mitigation: {alt.mitigation_score.toFixed(0)}</span>
                      <span>Similarity: {alt.similarity_score.toFixed(0)}%</span>
                      {alt.sourcing && <span>Supplier: {alt.sourcing.supplier_name}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
