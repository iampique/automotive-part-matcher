'use client';

import { useState } from 'react';
import SearchInput from '@/components/SearchInput';
import ResultsDisplay from '@/components/ResultsDisplay';
import { searchConnectors } from '@/lib/api';
import type { MatchResult, ExecutionStep } from '@/lib/types';
import { Zap, Workflow, Network } from 'lucide-react';
import Link from 'next/link';

export default function Home() {
  const [results, setResults] = useState<MatchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [executionTrace, setExecutionTrace] = useState<ExecutionStep[]>([]);
  const [totalTime, setTotalTime] = useState(0);
  const [acornUsed, setAcornUsed] = useState(false);

  const handleSearch = async (
    textInput?: string,
    file?: File,
    llmProvider?: 'claude' | 'openai',
    enableAcorn: boolean = true
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await searchConnectors({
        textInput,
        file,
        llmProvider,
        enableAcorn,
      });

      setResults(response.matches);
      setExecutionTrace(response.execution_trace || []);
      setTotalTime(response.processing_time_ms);
      setAcornUsed(response.acorn_used);
      
      // Log fallback status for debugging
      if (response.fallback_used) {
        console.warn(
          `⚠️ Fallback matching used: ${response.matches_passed_hard_requirements || 0} matches passed hard requirements. ` +
          `Showing ${response.matches.length} semantic matches instead.`
        );
      }

      console.log(`Search completed in ${response.processing_time_ms}ms`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(errorMessage);
      setResults([]);
      setExecutionTrace([]);
      setTotalTime(0);
      setAcornUsed(false);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Modern Header Section */}
      <header className="bg-white/80 backdrop-blur-lg border-b border-gray-200/50 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg shadow-lg">
                  <Zap className="w-6 h-6 text-white" />
                </div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 via-gray-800 to-gray-700 bg-clip-text text-transparent">
                  Automotive Connector Matcher
                </h1>
              </div>
              <div className="flex items-center space-x-4 ml-12">
                <p className="text-base text-gray-600">
                  Match connector requirements to the right parts in minutes—powered by intelligent search.
                </p>
<Link 
                href="/workflow" 
                className="md:hidden flex items-center space-x-1 px-3 py-1.5 bg-indigo-50 rounded-lg border border-indigo-100 hover:border-indigo-200 transition-all text-sm"
              >
                <Workflow className="w-3.5 h-3.5 text-indigo-600" />
                <span className="text-indigo-700 font-medium">How it works</span>
              </Link>
              </div>
            </div>
            <div className="hidden md:flex items-center space-x-4">
              <Link 
                href="/disruption" 
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-red-50 to-orange-50 rounded-lg border border-red-100 hover:border-red-200 transition-all duration-200 hover:shadow-md"
              >
                <Zap className="w-4 h-4 text-red-600" />
                <span className="text-sm font-medium text-red-700">Disruption Demo</span>
              </Link>
              <Link 
                href="/graph" 
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-100 hover:border-purple-200 transition-all duration-200 hover:shadow-md"
              >
                <Network className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-700">Supplier Risk</span>
              </Link>
              <Link 
                href="/workflow" 
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg border border-indigo-100 hover:border-indigo-200 transition-all duration-200 hover:shadow-md"
              >
                <Workflow className="w-4 h-4 text-indigo-600" />
                <span className="text-sm font-medium text-indigo-700">How it works</span>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Search Input Section */}
        <section className="animate-fade-in">
          <SearchInput onSearch={handleSearch} isLoading={isLoading} />
        </section>

        {/* Results Display Section */}
        <section className="animate-fade-in">
          <ResultsDisplay
            results={results}
            isLoading={isLoading}
            error={error}
            executionTrace={executionTrace}
            totalTime={totalTime}
            acornUsed={acornUsed}
          />
        </section>
      </main>

      {/* Modern Footer Section */}
      <footer className="mt-20 bg-white/60 backdrop-blur-lg border-t border-gray-200/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0">
            <div className="flex items-center space-x-6">
              <Link 
                href="/workflow" 
                className="flex items-center space-x-2 text-gray-600 hover:text-indigo-600 transition-colors"
              >
                <Workflow className="w-5 h-5" />
                <span className="text-sm font-medium">How it works</span>
              </Link>
            </div>
            <p className="text-sm text-gray-500">
              © {new Date().getFullYear()} Automotive Connector Matcher
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
