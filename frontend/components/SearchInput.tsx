'use client';

import { useState } from 'react';
import { Search, Upload, X, Settings, FileText, Sparkles, ChevronDown } from 'lucide-react';

interface SearchInputProps {
  onSearch: (
    textInput?: string,
    file?: File,
    llmProvider?: 'claude' | 'openai',
    enableAcorn?: boolean
  ) => void;
  isLoading: boolean;
}

export default function SearchInput({ onSearch, isLoading }: SearchInputProps) {
  const [activeTab, setActiveTab] = useState<'text' | 'file'>('text');
  const [textInput, setTextInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [llmProvider, setLlmProvider] = useState<'claude' | 'openai'>('claude');
  const [enableAcorn, setEnableAcorn] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = () => {
    if (activeTab === 'text') {
      if (textInput.trim() !== '') {
        onSearch(textInput, undefined, llmProvider, enableAcorn);
      }
    } else if (activeTab === 'file') {
      if (selectedFile) {
        onSearch(undefined, selectedFile, llmProvider, enableAcorn);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    const fileInput = document.getElementById('file-input') as HTMLInputElement;
    if (fileInput) {
      fileInput.value = '';
    }
  };

  const isSearchDisabled =
    isLoading ||
    (activeTab === 'text' && textInput.trim() === '') ||
    (activeTab === 'file' && !selectedFile);

  return (
    <div className="w-full max-w-5xl mx-auto">
      <div className="bg-white/90 backdrop-blur-xl rounded-2xl shadow-xl border border-gray-200/50 overflow-hidden">
        {/* Tab Switcher - Modern Design */}
        <div className="flex border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100/50">
          <button
            onClick={() => setActiveTab('text')}
            className={`flex-1 px-6 py-4 font-semibold text-sm transition-all duration-200 relative ${
              activeTab === 'text'
                ? 'text-blue-600 bg-white shadow-sm'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <FileText className={`w-5 h-5 ${activeTab === 'text' ? 'text-blue-600' : 'text-gray-400'}`} />
              <span>Text Input</span>
            </div>
            {activeTab === 'text' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab('file')}
            className={`flex-1 px-6 py-4 font-semibold text-sm transition-all duration-200 relative ${
              activeTab === 'file'
                ? 'text-blue-600 bg-white shadow-sm'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <Upload className={`w-5 h-5 ${activeTab === 'file' ? 'text-blue-600' : 'text-gray-400'}`} />
              <span>Upload Document</span>
            </div>
            {activeTab === 'file' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
        </div>

        {/* Content Area */}
        <div className="p-6 md:p-8">
          {activeTab === 'text' ? (
            <div className="mb-6">
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                Describe your connector requirements
              </label>
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Example: Need 48-pin connector for EV battery, 48V rated, IP67 protection, automotive grade with IATF 16949. Operating temperature -40°C to 125°C, lead time under 45 days."
                rows={8}
                className="w-full px-5 py-4 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 resize-y text-gray-900 bg-white shadow-sm hover:shadow-md"
              />
              <div className="mt-3 flex items-center justify-between">
                <p className="text-xs text-gray-500">
                  {textInput.length > 0 && `${textInput.length} characters`}
                </p>
                <div className="flex items-center space-x-2 text-xs text-gray-500">
                  <Sparkles className="w-4 h-4" />
                  <span>Smart parsing</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="mb-6">
              {selectedFile ? (
                <div className="border-2 border-dashed border-blue-300 rounded-xl p-6 bg-gradient-to-br from-blue-50 to-indigo-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 bg-blue-100 rounded-lg">
                        <FileText className="w-6 h-6 text-blue-600" />
                      </div>
                      <div>
                        <p className="text-gray-900 font-semibold">{selectedFile.name}</p>
                        <p className="text-sm text-gray-600">
                          {(selectedFile.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={handleClearFile}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
                      aria-label="Clear file"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              ) : (
                <label
                  htmlFor="file-input"
                  className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl p-12 text-center hover:border-blue-400 hover:bg-blue-50/50 transition-all duration-200 cursor-pointer group"
                >
                  <div className="p-4 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full mb-4 group-hover:scale-110 transition-transform duration-200">
                    <Upload className="w-8 h-8 text-blue-600" />
                  </div>
                  <input
                    id="file-input"
                    type="file"
                    accept=".pdf,.docx"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <span className="inline-block px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg cursor-pointer hover:from-blue-700 hover:to-indigo-700 transition-all duration-200 font-semibold shadow-lg hover:shadow-xl mb-2">
                    Choose File
                  </span>
                  <p className="mt-2 text-sm text-gray-500">
                    Supported formats: PDF, DOCX (Max size: 10MB)
                  </p>
                </label>
              )}
            </div>
          )}

          {/* Advanced Configuration - Modern Accordion */}
          <div className="mb-6">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-xl transition-all duration-200 group"
            >
              <div className="flex items-center space-x-3">
                <Settings className="w-5 h-5 text-gray-600 group-hover:text-blue-600 transition-colors" />
                <span className="text-sm font-semibold text-gray-700">
                  Advanced Options
                </span>
              </div>
              <ChevronDown
                className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${
                  showAdvanced ? 'rotate-180' : ''
                }`}
              />
            </button>

            {showAdvanced && (
              <div className="mt-4 p-6 bg-gradient-to-br from-gray-50 to-blue-50/30 rounded-xl border border-gray-200 space-y-5 animate-fade-in">
                {/* LLM Provider */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    AI Model
                  </label>
                  <select
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value as 'claude' | 'openai')}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-white font-medium"
                  >
                    <option value="claude">Anthropic</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </div>

                {/* ACORN Toggle */}
                <div className="flex items-start space-x-4 p-4 bg-white rounded-lg border-2 border-gray-200">
                  <input
                    type="checkbox"
                    id="acorn-toggle"
                    checked={enableAcorn}
                    onChange={(e) => setEnableAcorn(e.target.checked)}
                    className="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 mt-0.5 cursor-pointer"
                  />
                  <div className="flex-1">
                    <label htmlFor="acorn-toggle" className="text-sm font-semibold text-gray-900 cursor-pointer block">
                      Higher accuracy search
                    </label>
                    <p className="text-xs text-gray-600 mt-1">
                      Improves match quality for complex requirements. May take a bit longer.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Search Button - Modern Design */}
          <div className="flex justify-end">
            <button
              onClick={handleSubmit}
              disabled={isSearchDisabled}
              className={`group relative flex items-center space-x-3 px-8 py-4 rounded-xl font-semibold text-base transition-all duration-200 transform ${
                isSearchDisabled
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95'
              }`}
            >
              {!isLoading ? (
                <>
                  <Search className="w-5 h-5" />
                  <span>Search Connectors</span>
                </>
              ) : (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Searching...</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
