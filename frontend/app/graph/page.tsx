'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Loader2, AlertTriangle, Truck } from 'lucide-react';
import { getSupplierRisk, getSupplierSpof, getHealth } from '@/lib/api';
import type { SupplierRiskEntry, SpofEntry } from '@/lib/types';

export default function GraphDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [neo4jStatus, setNeo4jStatus] = useState<string>('unknown');
  const [suppliers, setSuppliers] = useState<SupplierRiskEntry[]>([]);
  const [spofEntries, setSpofEntries] = useState<SpofEntry[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const health = await getHealth();
        setNeo4jStatus(health.neo4j || 'disabled');
        if (health.neo4j !== 'connected') {
          setError('Neo4j is not connected. Configure AuraDB and run ingest_graph.py.');
          return;
        }
        const [risk, spof] = await Promise.all([getSupplierRisk(), getSupplierSpof()]);
        setSuppliers(risk.suppliers);
        setSpofEntries(spof.entries);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load supplier dashboard');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-purple-50">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-purple-700 hover:text-purple-900 font-medium mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Search
        </Link>

        <div className="flex items-center gap-3 mb-8">
          <Truck className="w-8 h-8 text-purple-600" />
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Supplier Risk Dashboard</h1>
            <p className="text-gray-600">Concentration risk and single points of failure</p>
          </div>
          {neo4jStatus !== 'connected' && (
            <span className="ml-auto text-xs font-semibold text-amber-700 bg-amber-100 px-3 py-1 rounded-full">
              Neo4j: {neo4jStatus}
            </span>
          )}
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-10 h-10 animate-spin text-purple-600" />
          </div>
        ) : error ? (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 flex gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0" />
            <p className="text-amber-900">{error}</p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-8">
            <section className="bg-white rounded-2xl shadow-lg border p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Concentration Risk</h2>
              <div className="space-y-3">
                {suppliers.map((s) => (
                  <div key={s.supplier_id} className="border rounded-lg p-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-semibold">{s.supplier_name}</p>
                        <p className="text-sm text-gray-500">{s.region} · Tier {s.tier}</p>
                      </div>
                      <span className="text-sm font-bold text-purple-700">
                        Risk {s.risk_score}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-gray-600 grid grid-cols-3 gap-2">
                      <span>{s.critical_parts} parts</span>
                      <span>{s.critical_assemblies} assemblies</span>
                      <span>{s.sole_source_count} sole-source</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-white rounded-2xl shadow-lg border p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Single Points of Failure</h2>
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {spofEntries.slice(0, 20).map((e) => (
                  <div key={e.part_number} className="border border-red-200 bg-red-50 rounded-lg p-4 text-sm">
                    <p className="font-semibold text-red-900">{e.part_number}</p>
                    <p className="text-red-800">{e.connector_name}</p>
                    <p className="text-red-700 mt-1">Supplier: {e.supplier_name}</p>
                    <p className="text-gray-600 mt-1">
                      Vehicles: {e.affected_vehicles.slice(0, 3).join(', ')}
                    </p>
                  </div>
                ))}
                {spofEntries.length === 0 && (
                  <p className="text-gray-500">No sole-source critical parts found.</p>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
