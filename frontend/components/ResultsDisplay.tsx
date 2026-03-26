'use client';

import MatchCard from './MatchCard';
import WorkflowTrace from './WorkflowTrace';
import type { MatchResult, ExecutionStep } from '@/lib/types';
import { CheckCircle, AlertCircle, Search, Sparkles } from 'lucide-react';

interface ResultsDisplayProps {
  results: MatchResult[];
  isLoading: boolean;
  error: string | null;
  executionTrace?: ExecutionStep[];
  totalTime?: number;
  acornUsed?: boolean;
}

export default function ResultsDisplay({
  results,
  isLoading,
  error,
  executionTrace,
  totalTime,
  acornUsed,
}: ResultsDisplayProps) {
  // Loading State - Modern Design
  if (isLoading) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-20 px-4">
        <div className="relative mb-6">
          <div className="w-20 h-20 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-blue-600 animate-pulse" />
          </div>
        </div>
        <h3 className="text-2xl font-bold text-gray-800 mb-2">Searching for matches...</h3>
        <p className="text-gray-600 text-center max-w-md">
          Analyzing requirements and finding the best connector matches.
        </p>
      </div>
    );
  }

  // Error State - Modern Design
  if (error) {
    return (
      <div className="w-full max-w-4xl mx-auto animate-fade-in">
        <div className="bg-gradient-to-br from-red-50 to-orange-50 border-2 border-red-200 rounded-2xl p-8 text-center shadow-lg">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
            <AlertCircle className="w-8 h-8 text-red-600" />
          </div>
          <h3 className="text-2xl font-bold text-red-800 mb-3">Search Error</h3>
          <p className="text-red-700 mb-6 text-lg">{error}</p>
          <p className="text-sm text-red-600">
            Please check your input and try again, or contact support if the issue persists.
          </p>
        </div>
      </div>
    );
  }

  // Empty State - Modern Design
  if (results.length === 0) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-20 px-4 animate-fade-in">
        <div className="w-24 h-24 mb-6 bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center shadow-lg">
          <Search className="w-12 h-12 text-gray-400" />
        </div>
        <h3 className="text-2xl font-bold text-gray-800 mb-3">No matches yet</h3>
        <p className="text-gray-600 text-center max-w-lg mb-2 text-lg">
          Enter detailed requirements or upload a document to search for matching connectors.
        </p>
        <p className="text-sm text-gray-500 text-center max-w-lg">
          Try describing specifications like pin count, voltage rating, IP protection, operating temperature range, and certifications.
        </p>
      </div>
    );
  }

  // Results State - Modern Design
  // Check if any matches are fallback matches
  const hasFallbackMatches = results.some(m => m.is_fallback_match);
  const fallbackCount = results.filter(m => m.is_fallback_match).length;
  
  return (
    <div className="w-full max-w-7xl mx-auto px-4 animate-fade-in">
      {/* Fallback Warning Banner */}
      {hasFallbackMatches && (
        <div className="mb-6 bg-yellow-50 border-2 border-yellow-400 rounded-xl p-4 flex items-start space-x-3 shadow-md">
          <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="font-bold text-yellow-900 mb-1">Close alternatives</h4>
            <p className="text-sm text-yellow-800">
              {fallbackCount} of {results.length} results are close alternatives that may not meet every requirement. 
              Please review specifications to confirm fit.
            </p>
          </div>
        </div>
      )}
      
      {/* Header Section - Enhanced */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-4xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent mb-2">
              Match Results
            </h2>
            <div className="flex items-center space-x-4">
              <p className="text-lg text-gray-600">
                Found <span className="font-bold text-blue-600">{results.length}</span> matching connector{results.length !== 1 ? 's' : ''}
              </p>
              {acornUsed && (
                <span className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-100 text-blue-700 text-sm font-semibold rounded-full">
                  <Sparkles className="w-4 h-4" />
                  <span>Enhanced search</span>
                </span>
              )}
            </div>
          </div>
          {totalTime !== undefined && (
            <div className="hidden md:flex items-center space-x-2 px-4 py-2 bg-gray-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-sm font-semibold text-gray-700">
                {(totalTime / 1000).toFixed(2)}s
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Workflow Trace */}
      {executionTrace && executionTrace.length > 0 && totalTime !== undefined && (
        <div className="mb-10">
          <WorkflowTrace
            steps={executionTrace}
            totalTime={totalTime}
            acornUsed={acornUsed ?? false}
          />
        </div>
      )}

      {/* Results Grid - Enhanced */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
        {results.map((match, index) => (
          <div
            key={match.part_number}
            className="animate-fade-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <MatchCard match={match} />
          </div>
        ))}
      </div>
    </div>
  );
}
