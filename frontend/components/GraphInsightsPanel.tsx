'use client';

import { useEffect, useState } from 'react';
import {
  X,
  Loader2,
  AlertTriangle,
  Car,
  Layers,
  Shield,
  Truck,
  Network,
  Zap,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import type { DisruptionResponse, MatchResult, MitigationCandidate, PartSourcing } from '@/lib/types';
import {
  getPartImpact,
  getConnectorCompliance,
  getPartSourcing,
  getSupplierRisk,
  getSupplierSpof,
  getHealth,
  analyzeDisruption,
} from '@/lib/api';

interface GraphInsightsPanelProps {
  match: MatchResult;
  onClose: () => void;
}

type Tab = 'impact' | 'compliance' | 'suppliers' | 'mitigation';

const WORKFLOW_STEPS = [
  { id: 'analyze_impact', label: 'Impact Analysis' },
  { id: 'find_alternatives', label: 'Find Alternatives' },
  { id: 'validate_compliance', label: 'Validate Compliance' },
  { id: 'assess_supplier_risk', label: 'Supplier Risk' },
  { id: 'rank_mitigation', label: 'Rank Options' },
];

function verdictStyles(verdict: MitigationCandidate['verdict']) {
  if (verdict === 'preferred') {
    return {
      badge: 'bg-green-100 text-green-800 border-green-200',
      label: 'Preferred',
    };
  }
  if (verdict === 'caution') {
    return {
      badge: 'bg-amber-100 text-amber-800 border-amber-200',
      label: 'Caution',
    };
  }
  return {
    badge: 'bg-red-100 text-red-800 border-red-200',
    label: 'Not Recommended',
  };
}

export default function GraphInsightsPanel({ match, onClose }: GraphInsightsPanelProps) {
  const [tab, setTab] = useState<Tab>('impact');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [neo4jStatus, setNeo4jStatus] = useState<string>('unknown');
  const [impact, setImpact] = useState<Awaited<ReturnType<typeof getPartImpact>> | null>(null);
  const [compliance, setCompliance] = useState<Awaited<ReturnType<typeof getConnectorCompliance>> | null>(null);
  const [supplierRisk, setSupplierRisk] = useState<Awaited<ReturnType<typeof getSupplierRisk>> | null>(null);
  const [partSourcing, setPartSourcing] = useState<PartSourcing | null>(null);
  const [spof, setSpof] = useState<Awaited<ReturnType<typeof getSupplierSpof>> | null>(null);
  const [disruption, setDisruption] = useState<DisruptionResponse | null>(null);
  const [disruptionLoading, setDisruptionLoading] = useState(false);
  const [disruptionError, setDisruptionError] = useState<string | null>(null);

  const partNumber = match.connector.part_number;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const health = await getHealth();
        if (cancelled) return;
        setNeo4jStatus(health.neo4j || 'disabled');

        if (health.neo4j === 'disabled' || health.neo4j === 'disconnected') {
          setError(
            health.neo4j === 'disabled'
              ? 'Graph features are disabled. Configure NEO4J_URI in backend/.env and run ingest_graph.py.'
              : 'Cannot connect to Neo4j. Check AuraDB credentials.'
          );
          return;
        }

        const [impactData, complianceData, sourcingData, riskData, spofData] = await Promise.all([
          getPartImpact(partNumber),
          getConnectorCompliance(partNumber),
          getPartSourcing(partNumber).catch(() => null),
          getSupplierRisk(),
          getSupplierSpof(),
        ]);

        if (!cancelled) {
          setImpact(impactData);
          setCompliance(complianceData);
          setPartSourcing(sourcingData);
          setSupplierRisk(riskData);
          setSpof(spofData);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load graph insights');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [partNumber]);

  async function runDisruptionAnalysis() {
    setTab('mitigation');
    setDisruptionLoading(true);
    setDisruptionError(null);
    try {
      const result = await analyzeDisruption({
        part_number: partNumber,
        max_alternatives: 8,
        min_similarity: 55,
      });
      setDisruption(result);
    } catch (e) {
      setDisruptionError(e instanceof Error ? e.message : 'Disruption analysis failed');
    } finally {
      setDisruptionLoading(false);
    }
  }

  const tabs: { id: Tab; label: string; icon: typeof Car }[] = [
    { id: 'impact', label: 'Impact', icon: Car },
    { id: 'compliance', label: 'Compliance', icon: Shield },
    { id: 'suppliers', label: 'Supplier Risk', icon: Truck },
    { id: 'mitigation', label: 'Mitigation', icon: Zap },
  ];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col border border-gray-200">
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-indigo-50">
          <div>
            <div className="flex items-center gap-2">
              <Network className="w-6 h-6 text-purple-600" />
              <h3 className="text-2xl font-bold text-gray-900">Graph Insights</h3>
            </div>
            <p className="text-sm text-gray-600 mt-1">
              {partNumber} — {match.connector.name}
            </p>
            {neo4jStatus !== 'unknown' && neo4jStatus !== 'connected' && (
              <span className="inline-block mt-2 text-xs font-semibold text-amber-700 bg-amber-100 px-2 py-1 rounded">
                Neo4j: {neo4jStatus}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-white rounded-lg"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex border-b border-gray-200 px-4 overflow-x-auto">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
                tab === id
                  ? 'border-purple-600 text-purple-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {loading && tab !== 'mitigation' ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="w-12 h-12 animate-spin text-purple-600 mb-4" />
              <p className="text-gray-600">Querying graph database...</p>
            </div>
          ) : error && tab !== 'mitigation' ? (
            <div className="bg-amber-50 border-2 border-amber-200 rounded-xl p-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0" />
                <p className="text-amber-900">{error}</p>
              </div>
            </div>
          ) : tab === 'impact' && impact ? (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                  <p className="text-xs font-semibold text-red-600 uppercase">Affected Vehicles</p>
                  <p className="text-3xl font-bold text-red-900">{impact.affected_vehicles.length}</p>
                </div>
                <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
                  <p className="text-xs font-semibold text-orange-600 uppercase">Total BOM Qty</p>
                  <p className="text-3xl font-bold text-orange-900">{impact.total_bom_qty}</p>
                </div>
              </div>

              {impact.critical_paths.length > 0 && (
                <div>
                  <h4 className="font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                    Critical Paths
                  </h4>
                  <ul className="space-y-1">
                    {impact.critical_paths.map((path, i) => (
                      <li key={i} className="text-sm text-red-800 bg-red-50 px-3 py-2 rounded-lg">
                        {path}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h4 className="font-bold text-gray-900 mb-2 flex items-center gap-2">
                  <Car className="w-4 h-4" />
                  Vehicles
                </h4>
                <div className="grid gap-2">
                  {impact.affected_vehicles.map((v) => (
                    <div key={v.id} className="bg-gray-50 border rounded-lg p-3 text-sm">
                      <span className="font-semibold">{v.name}</span>
                      <span className="text-gray-500 ml-2">
                        {v.platform} · {v.model_year}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-bold text-gray-900 mb-2 flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  Assemblies
                </h4>
                <div className="grid gap-2">
                  {impact.affected_assemblies.map((a) => (
                    <div key={a.id} className="bg-gray-50 border rounded-lg p-3 text-sm flex justify-between">
                      <span>
                        <span className="font-semibold">{a.name}</span>
                        <span className="text-gray-500 ml-2">({a.criticality})</span>
                      </span>
                      <span className="text-gray-600">qty {a.qty}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : tab === 'compliance' && compliance ? (
            <div className="space-y-6">
              <div>
                <h4 className="font-bold text-gray-900 mb-2">Certifications</h4>
                <div className="flex flex-wrap gap-2">
                  {compliance.certifications.map((c) => (
                    <span key={c} className="bg-green-100 text-green-800 px-3 py-1 rounded-lg text-sm font-medium">
                      {c}
                    </span>
                  ))}
                  {compliance.certifications.length === 0 && (
                    <span className="text-gray-500 text-sm">None recorded</span>
                  )}
                </div>
              </div>

              <div>
                <h4 className="font-bold text-gray-900 mb-2">Inherited Requirements</h4>
                <div className="space-y-2">
                  {compliance.requirements.map((r) => (
                    <div key={`${r.id}-${r.source_assembly_id}`} className="bg-gray-50 border rounded-lg p-3 text-sm">
                      <span className="font-semibold">{r.name}</span>
                      <span className="text-gray-500 ml-2">via {r.source_assembly_name}</span>
                      {r.inherited_from && (
                        <span className="text-purple-600 ml-2">← {r.inherited_from}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {compliance.gaps.length > 0 && (
                <div>
                  <h4 className="font-bold text-red-700 mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    Compliance Gaps
                  </h4>
                  <div className="space-y-2">
                    {compliance.gaps.map((g) => (
                      <div key={g.requirement_id} className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
                        Missing <strong>{g.requirement_name}</strong> required by {g.source_assembly_name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : tab === 'suppliers' && supplierRisk && spof ? (
            <div className="space-y-6">
              {partSourcing && (
                <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
                  <h4 className="font-bold text-indigo-900 mb-2">This Part&apos;s Supplier</h4>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <div>
                      <span className="font-semibold text-gray-900">{partSourcing.supplier_name}</span>
                      <span className="text-gray-500 ml-2">{partSourcing.region} · Tier {partSourcing.tier}</span>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <span className="bg-white border border-indigo-200 px-2 py-1 rounded-lg font-semibold text-indigo-800">
                        {partSourcing.share_pct.toFixed(0)}% share
                      </span>
                      {partSourcing.sole_source ? (
                        <span className="bg-red-100 text-red-800 border border-red-200 px-2 py-1 rounded-lg font-semibold">
                          Sole source
                        </span>
                      ) : (
                        <span className="bg-green-100 text-green-800 border border-green-200 px-2 py-1 rounded-lg font-semibold">
                          Dual-source eligible
                        </span>
                      )}
                    </div>
                  </div>
                  {partSourcing.share_pct >= 90 && !partSourcing.sole_source && (
                    <p className="text-xs text-amber-800 mt-2">
                      High concentration ({partSourcing.share_pct.toFixed(0)}%) — not formal sole-source but worth monitoring.
                    </p>
                  )}
                </div>
              )}

              <div>
                <h4 className="font-bold text-gray-900 mb-2">Platform Concentration Risk</h4>
                <p className="text-xs text-gray-500 mb-2">Fleet-wide critical parts exposure across all suppliers</p>
                <div className="space-y-2">
                  {supplierRisk.suppliers.slice(0, 5).map((s) => (
                    <div key={s.supplier_id} className="bg-gray-50 border rounded-lg p-3 text-sm flex justify-between items-center">
                      <div>
                        <span className="font-semibold">{s.supplier_name}</span>
                        <span className="text-gray-500 ml-2">{s.region}</span>
                      </div>
                      <div className="text-right text-xs text-gray-600">
                        <div>{s.critical_parts} critical parts</div>
                        <div>{s.sole_source_count} sole-source</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-bold text-gray-900 mb-2">Single Points of Failure (this part)</h4>
                {spof.entries.filter((e) => e.part_number === partNumber).length > 0 ? (
                  spof.entries
                    .filter((e) => e.part_number === partNumber)
                    .map((e) => (
                      <div key={e.part_number} className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm">
                        <p className="font-semibold text-red-900">Sole source: {e.supplier_name}</p>
                        <p className="text-red-700 mt-1">
                          Affects: {e.affected_vehicles.join(', ') || 'N/A'}
                        </p>
                      </div>
                    ))
                ) : (
                  <p className="text-gray-600 text-sm bg-gray-50 border rounded-lg p-4">
                    This part is not flagged as a sole-source critical SPOF.
                  </p>
                )}
              </div>
            </div>
          ) : tab === 'mitigation' ? (
            <div className="space-y-6">
              {!disruption && !disruptionLoading && (
                <div className="text-center py-12 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl border border-purple-100">
                  <Zap className="w-12 h-12 text-purple-600 mx-auto mb-4" />
                  <h4 className="text-xl font-bold text-gray-900 mb-2">Supply Disruption Mitigation</h4>
                  <p className="text-gray-600 max-w-lg mx-auto mb-6">
                    Run the full orchestrated workflow: impact analysis → vector alternatives →
                    compliance validation → supplier risk → ranked substitutes.
                  </p>
                  <button
                    onClick={runDisruptionAnalysis}
                    className="inline-flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold px-6 py-3 rounded-xl shadow-lg"
                  >
                    <Zap className="w-5 h-5" />
                    Analyze Disruption
                  </button>
                </div>
              )}

              {disruptionLoading && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 text-purple-700 font-semibold">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Running disruption workflow...
                  </div>
                  <div className="grid gap-2">
                    {WORKFLOW_STEPS.map((step) => (
                      <div
                        key={step.id}
                        className="flex items-center gap-3 bg-purple-50 border border-purple-100 rounded-lg px-4 py-3 text-sm animate-pulse"
                      >
                        <Clock className="w-4 h-4 text-purple-500" />
                        <span>{step.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {disruptionError && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800">
                  {disruptionError}
                </div>
              )}

              {disruption && (
                <>
                  <div className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl p-5">
                    <p className="text-sm font-medium opacity-90 mb-1">Executive Summary</p>
                    <p className="text-lg font-semibold leading-relaxed">{disruption.summary}</p>
                    <p className="text-xs mt-3 opacity-75">
                      Completed in {disruption.processing_time_ms.toFixed(0)}ms
                    </p>
                  </div>

                  {disruption.warnings.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900">
                      {disruption.warnings.map((w, i) => (
                        <p key={i}>{w}</p>
                      ))}
                    </div>
                  )}

                  <div>
                    <h4 className="font-bold text-gray-900 mb-3">Workflow Steps</h4>
                    <div className="space-y-2">
                      {disruption.execution_trace.map((step) => (
                        <div
                          key={step.node}
                          className={`flex items-center justify-between text-sm border rounded-lg px-4 py-2 ${
                            step.status === 'success'
                              ? 'bg-green-50 border-green-100'
                              : 'bg-red-50 border-red-100'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            {step.status === 'success' ? (
                              <CheckCircle2 className="w-4 h-4 text-green-600" />
                            ) : (
                              <AlertTriangle className="w-4 h-4 text-red-600" />
                            )}
                            <span className="font-medium capitalize">{step.node.replace(/_/g, ' ')}</span>
                          </div>
                          <span className="text-gray-500 text-xs">{step.duration_ms.toFixed(0)}ms</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-bold text-gray-900 mb-3">Ranked Mitigation Options</h4>
                    {disruption.alternatives.length === 0 ? (
                      <p className="text-gray-600 bg-gray-50 border rounded-lg p-4">
                        No alternatives met the similarity threshold.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {disruption.alternatives.map((alt) => {
                          const vs = verdictStyles(alt.verdict);
                          return (
                            <div
                              key={alt.part_number}
                              className={`border rounded-xl p-4 ${vs.badge.split(' ')[0]} border-opacity-50`}
                            >
                              <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                                <div>
                                  <p className="font-bold text-gray-900">{alt.part_number}</p>
                                  <p className="text-sm text-gray-600">{alt.name}</p>
                                </div>
                                <div className="flex gap-2 flex-wrap">
                                  <span className={`text-xs font-bold px-2 py-1 rounded border ${vs.badge}`}>
                                    {vs.label}
                                  </span>
                                  <span className="text-xs font-semibold bg-white/80 px-2 py-1 rounded border">
                                    Mitigation {alt.mitigation_score.toFixed(0)}
                                  </span>
                                  <span className="text-xs font-semibold bg-white/80 px-2 py-1 rounded border">
                                    Similarity {alt.similarity_score.toFixed(0)}%
                                  </span>
                                </div>
                              </div>
                              <p className="text-sm text-gray-700 mb-2">{alt.recommendation}</p>
                              <div className="flex flex-wrap gap-3 text-xs text-gray-600">
                                {alt.sourcing && (
                                  <span>
                                    Supplier: {alt.sourcing.supplier_name}
                                    {alt.sourcing.sole_source && ' (sole source)'}
                                  </span>
                                )}
                                {alt.critical_compliance_gaps.length > 0 && (
                                  <span className="text-red-700">
                                    {alt.critical_compliance_gaps.length} critical compliance gap(s)
                                  </span>
                                )}
                                {alt.is_spof && <span className="text-red-700">SPOF flagged</span>}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          ) : null}
        </div>

        <div className="border-t border-gray-200 p-4 bg-gray-50 flex gap-3">
          {!loading && !error && tab !== 'mitigation' && (
            <button
              onClick={runDisruptionAnalysis}
              className="flex-1 inline-flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-4 rounded-xl shadow"
            >
              <Zap className="w-5 h-5" />
              Analyze Disruption
            </button>
          )}
          <button
            onClick={onClose}
            className={`${!loading && !error && tab !== 'mitigation' ? '' : 'w-full '} bg-white hover:bg-gray-100 text-gray-800 font-semibold py-3 px-4 rounded-xl border border-gray-200`}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
