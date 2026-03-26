'use client';

import { useEffect, useRef, useState } from 'react';
import { getWorkflowDiagram } from '@/lib/api';
import type { WorkflowDiagram } from '@/lib/types';
import { Loader2, AlertCircle } from 'lucide-react';

export default function WorkflowPage() {
  const [diagram, setDiagram] = useState<WorkflowDiagram | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mermaidRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadDiagram() {
      try {
        setLoading(true);
        const data = await getWorkflowDiagram();
        setDiagram(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load workflow diagram');
      } finally {
        setLoading(false);
      }
    }

    loadDiagram();
  }, []);

  useEffect(() => {
    if (!diagram?.mermaid_code || !mermaidRef.current) return;

    let cancelled = false;

    const container = mermaidRef.current;
    container.innerHTML = ''; // clear so only one diagram is ever shown

    import('mermaid')
      .then((mermaidModule) => {
        if (cancelled || !container.isConnected) return;

        const mermaid = mermaidModule.default;
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
            curve: 'basis',
            padding: 20,
            nodeSpacing: 50,
            rankSpacing: 70,
          },
          themeVariables: {
            fontSize: '16px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          },
        });

        if (cancelled || !container.isConnected) return;

        const element = document.createElement('div');
        const uniqueId = 'mermaid-diagram-' + Date.now();
        element.id = uniqueId;
        element.className = 'mermaid';
        element.textContent = diagram.mermaid_code;
        container.appendChild(element);

        if (typeof mermaid.run === 'function') {
          mermaid.run({ nodes: [element] }).catch((err: Error) => {
            if (!cancelled) {
              console.error('Mermaid render error:', err);
              setError('Failed to render diagram. Please check the console for details.');
            }
          });
        } else {
          (mermaid.render as unknown as (
            id: string,
            code: string,
            cb: (svgCode: string) => void
          ) => void)(uniqueId, diagram.mermaid_code, (svgCode: string) => {
            if (!cancelled) element.innerHTML = svgCode;
          });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Failed to load Mermaid:', err);
          setError('Failed to load Mermaid library. Please check the console for details.');
        }
      });

    return () => {
      cancelled = true;
      container.innerHTML = '';
    };
  }, [diagram]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <header className="bg-white/80 backdrop-blur-lg border-b border-gray-200/50 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg shadow-lg">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6 text-white">
                <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"></path>
              </svg>
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 via-gray-800 to-gray-700 bg-clip-text text-transparent">
              How matching works
            </h1>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
            <span className="ml-3 text-gray-600">Loading workflow diagram...</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border-2 border-red-200 rounded-xl p-6 mb-6 flex items-start space-x-3">
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-bold text-red-900 mb-1">Error Loading Diagram</h3>
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        )}

        {diagram && !loading && (
          <div className="bg-white/90 backdrop-blur-xl rounded-2xl shadow-xl border border-gray-200/50 p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Connector matching process</h2>
              <p className="text-gray-600">
                This diagram shows how we match your requirements to connectors: we understand your requirements, 
                find candidate parts, score and rank them, then return the best matches.
              </p>
            </div>
            
            <div className="w-full overflow-x-auto bg-gray-50 rounded-lg p-8">
              <div 
                ref={mermaidRef} 
                className="flex justify-center items-center w-full py-4"
              />
            </div>
            
          </div>
        )}
      </main>
    </div>
  );
}

