'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Award, Info, Search, X, Loader2, Zap, CheckCircle2, Clock, Shield, DollarSign, AlertTriangle, Network } from 'lucide-react';
import type { MatchResult, SimilarConnector } from '@/lib/types';
import { findSimilarConnectors } from '@/lib/api';
import GraphInsightsPanel from './GraphInsightsPanel';

interface MatchCardProps {
  match: MatchResult;
}

function getScoreColor(score: number): { bg: string; text: string; border: string; badge: string } {
  if (score >= 90) {
    return {
      bg: 'bg-gradient-to-br from-green-50 to-emerald-50',
      text: 'text-green-700',
      border: 'border-green-200',
      badge: 'bg-gradient-to-r from-green-500 to-emerald-600'
    };
  } else if (score >= 70) {
    return {
      bg: 'bg-gradient-to-br from-yellow-50 to-amber-50',
      text: 'text-yellow-700',
      border: 'border-yellow-200',
      badge: 'bg-gradient-to-r from-yellow-500 to-amber-600'
    };
  } else if (score >= 50) {
    return {
      bg: 'bg-gradient-to-br from-orange-50 to-red-50',
      text: 'text-orange-700',
      border: 'border-orange-200',
      badge: 'bg-gradient-to-r from-orange-500 to-red-600'
    };
  } else {
    return {
      bg: 'bg-gradient-to-br from-red-50 to-pink-50',
      text: 'text-red-700',
      border: 'border-red-200',
      badge: 'bg-gradient-to-r from-red-500 to-pink-600'
    };
  }
}

export default function MatchCard({ match }: MatchCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showSimilar, setShowSimilar] = useState(false);
  const [similarConnectors, setSimilarConnectors] = useState<SimilarConnector[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  const [similarError, setSimilarError] = useState<string | null>(null);
  const [showGraph, setShowGraph] = useState(false);
  
  const { connector, match_score, match_explanation } = match;
  const { specifications, certifications, applications, pricing } = connector;

  const scoreColors = getScoreColor(match_score);

  const handleFindSimilar = async () => {
    setLoadingSimilar(true);
    setSimilarError(null);
    setShowSimilar(true);
    
    try {
      const response = await findSimilarConnectors(connector.part_number, 5, true);
      setSimilarConnectors(response.similar_connectors);
    } catch (error) {
      setSimilarError(error instanceof Error ? error.message : 'Failed to find similar connectors');
      setSimilarConnectors([]);
    } finally {
      setLoadingSimilar(false);
    }
  };

  return (
    <>
      <div className="group bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden border border-gray-200/50 hover:border-blue-300/50 transform hover:-translate-y-1">
        {/* Score Badge - Top Right */}
        <div className="relative">
          <div className={`absolute top-4 right-4 ${scoreColors.badge} text-white px-4 py-2 rounded-xl font-bold text-lg shadow-lg z-10`}>
            {match_score.toFixed(1)}%
          </div>
        </div>

        {/* Fallback Match Badge - Top Left */}
        {match.is_fallback_match && (
          <div className="absolute top-4 left-4 bg-amber-500 text-white px-3 py-1.5 rounded-lg font-bold text-xs shadow-lg z-10 flex items-center space-x-1">
            <AlertTriangle className="w-4 h-4" />
            <span>Close match</span>
          </div>
        )}

        {/* Header Section */}
        <div className="p-6 pb-4">
          <div className="mb-4">
            <h3 className={`text-2xl font-bold text-gray-900 mb-2 ${match.is_fallback_match ? 'pr-32' : 'pr-20'}`}>
              {connector.part_number}
            </h3>
            <p className="text-gray-600 font-medium">{connector.name}</p>
          </div>

          {/* Quick Specs Grid - Modern Design */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-gradient-to-br from-gray-50 to-gray-100/50 rounded-xl p-3 border border-gray-200">
              <div className="flex items-center space-x-2 mb-1">
                <Zap className="w-4 h-4 text-blue-600" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Pins</p>
              </div>
              <p className="text-lg font-bold text-gray-900">{specifications.pin_count}</p>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-gray-100/50 rounded-xl p-3 border border-gray-200">
              <div className="flex items-center space-x-2 mb-1">
                <Zap className="w-4 h-4 text-green-600" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Voltage</p>
              </div>
              <p className="text-lg font-bold text-gray-900">{specifications.voltage_rating}V</p>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-gray-100/50 rounded-xl p-3 border border-gray-200">
              <div className="flex items-center space-x-2 mb-1">
                <Zap className="w-4 h-4 text-orange-600" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Current</p>
              </div>
              <p className="text-lg font-bold text-gray-900">{specifications.current_rating}A</p>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-gray-100/50 rounded-xl p-3 border border-gray-200">
              <div className="flex items-center space-x-2 mb-1">
                <Shield className="w-4 h-4 text-purple-600" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">IP Rating</p>
              </div>
              <p className="text-lg font-bold text-gray-900">{specifications.ip_rating}</p>
            </div>
          </div>

          {/* Connector Type Badge */}
          <div className="mb-4">
            <span className="inline-flex items-center px-3 py-1.5 bg-blue-100 text-blue-700 text-xs font-semibold rounded-lg">
              {connector.connector_type}
            </span>
          </div>

          {/* Match Explanation - Enhanced */}
          <div className={`${scoreColors.bg} ${scoreColors.border} border-2 rounded-xl p-4 mb-4`}>
            <div className="flex items-start space-x-3">
              <Info className={`w-5 h-5 ${scoreColors.text} mt-0.5 flex-shrink-0`} />
              <p className={`text-sm ${scoreColors.text} leading-relaxed font-medium`}>{match_explanation}</p>
            </div>
          </div>
        </div>

        {/* Expand Button - Modern */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-center space-x-2 text-blue-600 hover:text-blue-700 font-semibold py-3 px-6 bg-gray-50 hover:bg-blue-50 transition-all duration-200 border-t border-gray-200"
        >
          <span>{expanded ? 'Hide Details' : 'View Full Details'}</span>
          {expanded ? (
            <ChevronUp className="w-5 h-5" />
          ) : (
            <ChevronDown className="w-5 h-5" />
          )}
        </button>

        {/* Detailed View - Enhanced */}
        {expanded && (
          <div className="px-6 py-6 bg-gradient-to-br from-gray-50 to-white border-t border-gray-200 animate-fade-in">
            {/* Technical Specifications */}
            <div className="mb-6">
              <h4 className="text-lg font-bold text-gray-900 mb-4 flex items-center space-x-2">
                <Zap className="w-5 h-5 text-blue-600" />
                <span>Technical Specifications</span>
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { label: 'Operating Temperature', value: `${specifications.min_operating_temp}°C to ${specifications.max_operating_temp}°C`, icon: Clock },
                  { label: 'Housing Material', value: specifications.housing_material, icon: Shield },
                  { label: 'Contact Material', value: specifications.contact_material, icon: Zap },
                  { label: 'Contact Plating', value: specifications.contact_plating, icon: Award },
                ].map(({ label, value, icon: Icon }) => (
                  <div key={label} className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
                    <div className="flex items-center space-x-2 mb-1">
                      <Icon className="w-4 h-4 text-gray-400" />
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
                    </div>
                    <p className="text-sm font-bold text-gray-900">{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Description */}
            {connector.description && (
              <div className="mb-6">
                <h4 className="text-lg font-bold text-gray-900 mb-3">Description</h4>
                <p className="text-sm text-gray-700 leading-relaxed bg-white p-4 rounded-lg border border-gray-200">{connector.description}</p>
              </div>
            )}

            {/* Certifications - Enhanced */}
            {certifications && certifications.length > 0 && (
              <div className="mb-6">
                <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center space-x-2">
                  <Award className="w-5 h-5 text-yellow-600" />
                  <span>Certifications</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {certifications.map((cert, index) => (
                    <span
                      key={index}
                      className="bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-700 px-4 py-2 rounded-lg text-xs font-semibold border border-blue-200 shadow-sm"
                    >
                      {cert}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Applications - Enhanced */}
            {applications && applications.length > 0 && (
              <div className="mb-6">
                <h4 className="text-lg font-bold text-gray-900 mb-3 flex items-center space-x-2">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  <span>Applications</span>
                </h4>
                <ul className="space-y-2">
                  {applications.map((app, index) => (
                    <li key={index} className="flex items-start space-x-2 text-sm text-gray-700 bg-white p-3 rounded-lg border border-gray-200">
                      <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                      <span>{app}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Pricing & Availability - Enhanced */}
            <div className="mb-6">
              <h4 className="text-lg font-bold text-gray-900 mb-4 flex items-center space-x-2">
                <DollarSign className="w-5 h-5 text-green-600" />
                <span>Pricing & Availability</span>
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-5 border-2 border-green-200 shadow-sm">
                  <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-2">Unit Price</p>
                  <p className="text-3xl font-bold text-green-900">
                    ${pricing.unit_price_usd.toFixed(2)}
                  </p>
                </div>
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-5 border-2 border-blue-200 shadow-sm">
                  <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-2">Lead Time</p>
                  <p className="text-3xl font-bold text-blue-900">
                    {pricing.lead_time_days} <span className="text-lg">days</span>
                  </p>
                </div>
              </div>
            </div>

            {/* Find Similar + Graph Insights */}
            <div className="border-t border-gray-200 pt-6 space-y-3">
              <button
                onClick={handleFindSimilar}
                disabled={loadingSimilar}
                className="w-full flex items-center justify-center space-x-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-500 text-white font-semibold py-4 px-6 rounded-xl transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed"
              >
                {loadingSimilar ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Finding Similar Connectors...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    <span>Find Similar Connectors</span>
                  </>
                )}
              </button>
              <button
                onClick={() => setShowGraph(true)}
                className="w-full flex items-center justify-center space-x-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-semibold py-4 px-6 rounded-xl transition-all duration-200 shadow-lg hover:shadow-xl"
              >
                <Network className="w-5 h-5" />
                <span>View Graph Insights</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Similar Connectors Modal - Enhanced */}
      {showSimilar && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col border border-gray-200">
            {/* Modal Header - Enhanced */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
              <div>
                <h3 className="text-2xl font-bold text-gray-900">Similar Connectors</h3>
                <p className="text-sm text-gray-600 mt-1">
                  Alternatives to <span className="font-semibold">{connector.part_number}</span> - {connector.name}
                </p>
              </div>
              <button
                onClick={() => {
                  setShowSimilar(false);
                  setSimilarError(null);
                }}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-white rounded-lg transition-all duration-200"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Content - Enhanced */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingSimilar ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="w-12 h-12 animate-spin text-blue-600 mb-4" />
                  <p className="text-gray-600 font-medium">Finding similar connectors...</p>
                </div>
              ) : similarError ? (
                <div className="bg-red-50 border-2 border-red-200 rounded-xl p-6">
                  <div className="flex items-center space-x-3">
                    <X className="w-6 h-6 text-red-600" />
                    <p className="text-red-800 font-semibold">{similarError}</p>
                  </div>
                </div>
              ) : similarConnectors.length === 0 ? (
                <div className="text-center py-16">
                  <Search className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-600 text-lg">No similar connectors found.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {similarConnectors.map((similar, index) => (
                    <div
                      key={similar.connector.part_number}
                      className="border-2 border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-lg transition-all duration-200 bg-white"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <h4 className="text-xl font-bold text-gray-900 mb-1">
                            {similar.connector.part_number}
                          </h4>
                          <p className="text-gray-600 font-medium">{similar.connector.name}</p>
                        </div>
                        <div className="bg-gradient-to-r from-blue-500 to-indigo-600 text-white px-4 py-2 rounded-lg font-bold shadow-lg">
                          {similar.similarity_score.toFixed(1)}%
                        </div>
                      </div>

                      <p className="text-sm text-gray-700 mb-4 italic bg-gray-50 p-3 rounded-lg border border-gray-200">
                        {similar.explanation}
                      </p>

                      {(similar.supplier || (similar.compliance_gaps && similar.compliance_gaps.length > 0) || similar.is_spof) && (
                        <div className="flex flex-wrap gap-2 mb-4">
                          {similar.supplier && (
                            <span className="text-xs font-medium bg-indigo-50 text-indigo-800 border border-indigo-200 px-2 py-1 rounded-lg">
                              Supplier: {similar.supplier.supplier_name}
                              {similar.supplier.sole_source ? ' (sole source)' : ''}
                            </span>
                          )}
                          {similar.compliance_gaps && similar.compliance_gaps.length > 0 && (
                            <span className="text-xs font-medium bg-red-50 text-red-800 border border-red-200 px-2 py-1 rounded-lg">
                              {similar.compliance_gaps.length} compliance gap(s)
                            </span>
                          )}
                          {similar.compliance_gaps && similar.compliance_gaps.length === 0 && similar.supplier && (
                            <span className="text-xs font-medium bg-green-50 text-green-800 border border-green-200 px-2 py-1 rounded-lg">
                              No compliance gaps
                            </span>
                          )}
                          {similar.is_spof && (
                            <span className="text-xs font-medium bg-red-50 text-red-800 border border-red-200 px-2 py-1 rounded-lg">
                              SPOF flagged
                            </span>
                          )}
                        </div>
                      )}

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                        {[
                          { label: 'Pins', value: similar.connector.specifications.pin_count },
                          { label: 'Voltage', value: `${similar.connector.specifications.voltage_rating}V` },
                          { label: 'Current', value: `${similar.connector.specifications.current_rating}A` },
                          { label: 'IP Rating', value: similar.connector.specifications.ip_rating },
                        ].map(({ label, value }) => (
                          <div key={label} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">{label}</p>
                            <p className="text-sm font-bold text-gray-900">{value}</p>
                          </div>
                        ))}
                      </div>

                      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                        <div className="flex items-center space-x-2">
                          <DollarSign className="w-5 h-5 text-green-600" />
                          <span className="text-lg font-bold text-gray-900">
                            ${similar.connector.pricing.unit_price_usd.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Clock className="w-5 h-5 text-blue-600" />
                          <span className="text-sm font-semibold text-gray-700">
                            {similar.connector.pricing.lead_time_days} days
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer - Enhanced */}
            <div className="border-t border-gray-200 p-4 bg-gray-50">
              <button
                onClick={() => {
                  setShowSimilar(false);
                  setSimilarError(null);
                }}
                className="w-full bg-white hover:bg-gray-100 text-gray-800 font-semibold py-3 px-4 rounded-xl transition-all duration-200 border border-gray-200 shadow-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {showGraph && (
        <GraphInsightsPanel match={match} onClose={() => setShowGraph(false)} />
      )}
    </>
  );
}
