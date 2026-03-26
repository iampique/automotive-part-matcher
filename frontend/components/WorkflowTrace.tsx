'use client';

import { useState } from 'react';
import { CheckCircle, Clock, AlertCircle, ChevronDown, ChevronUp, Sparkles, Zap, TrendingUp } from 'lucide-react';
import type { ExecutionStep } from '@/lib/types';

interface WorkflowTraceProps {
  steps: ExecutionStep[];
  totalTime: number;
  acornUsed: boolean;
}

const FRIENDLY_NODE_NAMES: Record<string, string> = {
  parse: 'Understand requirements',
  search: 'Find candidates',
  score: 'Score matches',
  rank: 'Rank results',
};

function formatNodeName(node: string): string {
  return FRIENDLY_NODE_NAMES[node] ?? node
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
}

function getNodeIcon(node: string) {
  const nodeLower = node.toLowerCase();
  if (nodeLower.includes('parse')) return Sparkles;
  if (nodeLower.includes('search')) return Zap;
  if (nodeLower.includes('score')) return TrendingUp;
  if (nodeLower.includes('rank')) return CheckCircle;
  return Clock;
}

export default function WorkflowTrace({
  steps,
  totalTime,
  acornUsed,
}: WorkflowTraceProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const totalDuration = steps.reduce((sum, step) => sum + step.duration_ms, 0);
  const maxDuration = Math.max(...steps.map((step) => step.duration_ms), 1);

  return (
    <div className="w-full bg-white rounded-2xl shadow-lg border border-gray-200/50 overflow-hidden">
      {/* Header - Enhanced */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-5 flex items-center justify-between hover:bg-gradient-to-r hover:from-gray-50 hover:to-blue-50 transition-all duration-200 group"
      >
        <div className="flex items-center space-x-4">
          <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg shadow-lg">
            <Clock className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">Workflow Execution</h3>
            <div className="flex items-center space-x-3 mt-1">
              <div className="flex items-center space-x-2 text-sm text-gray-600">
                <Clock className="w-4 h-4" />
                <span className="font-semibold">{formatDuration(totalTime)}</span>
              </div>
              <div className="h-4 w-px bg-gray-300"></div>
              <span className="text-sm text-gray-600">
                {steps.length} step{steps.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
          {acornUsed && (
            <span className="inline-flex items-center space-x-1 px-3 py-1.5 bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-700 text-xs font-bold rounded-full border border-blue-200">
              <Sparkles className="w-3 h-3" />
              <span>Enhanced search</span>
            </span>
          )}
        </div>
        <div className={`transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
          <ChevronDown className="w-6 h-6 text-gray-400 group-hover:text-gray-600" />
        </div>
      </button>

      {/* Expanded Content - Enhanced */}
      {isExpanded && (
        <div className="px-6 py-6 border-t border-gray-200 bg-gradient-to-br from-gray-50 to-white animate-fade-in">
          {/* Timeline - Enhanced */}
          <div className="relative mb-8">
            {/* Vertical line */}
            <div className="absolute left-8 top-0 bottom-0 w-1 bg-gradient-to-b from-blue-200 via-indigo-200 to-purple-200 rounded-full"></div>

            {/* Steps */}
            <div className="space-y-8">
              {steps.map((step, index) => {
                const isSuccess = step.status === 'success';
                const percentage = (step.duration_ms / maxDuration) * 100;
                const Icon = getNodeIcon(step.node);

                return (
                  <div key={index} className="relative flex items-start space-x-4">
                    {/* Icon - Enhanced */}
                    <div
                      className={`relative z-10 flex items-center justify-center w-16 h-16 rounded-xl border-2 shadow-lg ${
                        isSuccess
                          ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-500 text-green-600'
                          : 'bg-gradient-to-br from-red-50 to-pink-50 border-red-500 text-red-600'
                      }`}
                    >
                      {isSuccess ? (
                        <Icon className="w-7 h-7" />
                      ) : (
                        <AlertCircle className="w-7 h-7" />
                      )}
                    </div>

                    {/* Step Content - Enhanced */}
                    <div className="flex-1 pb-8">
                      <div
                        className={`p-5 rounded-xl border-2 shadow-md ${
                          isSuccess
                            ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200'
                            : 'bg-gradient-to-br from-red-50 to-pink-50 border-red-200'
                        }`}
                      >
                        {/* Header */}
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-bold text-gray-900 text-lg flex items-center space-x-2">
                            <span>{formatNodeName(step.node)}</span>
                            {step.acorn_used && (
                              <span className="inline-flex items-center space-x-1 px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
                                <Sparkles className="w-3 h-3" />
                                <span>Enhanced</span>
                              </span>
                            )}
                          </h4>
                          <div className="flex items-center space-x-2 text-sm bg-white px-3 py-1.5 rounded-lg shadow-sm">
                            <Clock className="w-4 h-4 text-gray-500" />
                            <span className="font-bold text-gray-900">
                              {formatDuration(step.duration_ms)}
                            </span>
                          </div>
                        </div>

                        {/* Output */}
                        <p className="text-sm text-gray-700 mb-4 leading-relaxed bg-white p-3 rounded-lg border border-gray-200">
                          {step.output}
                        </p>

                        {/* Progress Bar - Enhanced */}
                        <div className="w-full bg-gray-200 rounded-full h-2.5 shadow-inner">
                          <div
                            className={`h-2.5 rounded-full transition-all duration-500 shadow-sm ${
                              isSuccess 
                                ? 'bg-gradient-to-r from-green-500 to-emerald-600' 
                                : 'bg-gradient-to-r from-red-500 to-pink-600'
                            }`}
                            style={{ width: `${percentage}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Summary Section - Enhanced */}
          <div className="mt-8 pt-6 border-t-2 border-gray-200">
            <h4 className="text-lg font-bold text-gray-900 mb-4">Performance Summary</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Total Processing Time */}
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-5 border-2 border-blue-200 shadow-sm">
                <div className="flex items-center space-x-3 mb-2">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Clock className="w-5 h-5 text-blue-600" />
                  </div>
                  <h5 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Total Time</h5>
                </div>
                <p className="text-3xl font-bold text-gray-900">{formatDuration(totalTime)}</p>
              </div>

              {/* Steps Count */}
              <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-5 border-2 border-green-200 shadow-sm">
                <div className="flex items-center space-x-3 mb-2">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  </div>
                  <h5 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Steps Executed</h5>
                </div>
                <p className="text-3xl font-bold text-gray-900">{steps.length}</p>
              </div>

              {/* ACORN Status */}
              <div className={`rounded-xl p-5 border-2 shadow-sm ${
                acornUsed 
                  ? 'bg-gradient-to-br from-purple-50 to-indigo-50 border-purple-200' 
                  : 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200'
              }`}>
                <div className="flex items-center space-x-3 mb-2">
                  <div className={`p-2 rounded-lg ${
                    acornUsed ? 'bg-purple-100' : 'bg-gray-200'
                  }`}>
                    {acornUsed ? (
                      <Sparkles className="w-5 h-5 text-purple-600" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                  <h5 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Search Mode</h5>
                </div>
                {acornUsed ? (
                  <div>
                    <p className="text-xl font-bold text-purple-600 mb-1">Enhanced</p>
                    <p className="text-xs text-gray-600">
                      Higher accuracy matching
                    </p>
                  </div>
                ) : (
                  <p className="text-xl font-bold text-gray-400">Standard</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
