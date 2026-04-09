import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import './ModelsPage.css';

const providers = [
  { id: 'builtin', name: 'Built-in', icon: BuiltinIcon },
  { id: 'ollama', name: 'Ollama', icon: OllamaIcon },
  { id: 'lmstudio', name: 'LM Studio', icon: LMStudioIcon },
  { id: 'openai', name: 'OpenAI', icon: OpenAIIcon },
  { id: 'anthropic', name: 'Anthropic', icon: AnthropicIcon },
  { id: 'google', name: 'Google', icon: GoogleIcon },
];

function BuiltinIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
    </svg>
  );
}

function OllamaIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

function LMStudioIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  );
}

function OpenAIIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" />
    </svg>
  );
}

function AnthropicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.3041 3.541h-3.6718l6.696 16.918H24Zm-10.6082 0L0 20.459h3.7442l1.3693-3.5527h7.0052l1.3693 3.5528h3.7442L10.5363 3.5409Zm-.3712 10.2232 2.2914-5.9456 2.2914 5.9456Z" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81" />
    </svg>
  );
}

function ModelsPage() {
  const { modelName, modelProvider, setModelInfo, baseUrl } = useApp();
  const [selectedProvider, setSelectedProvider] = useState('ollama');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [baseUrlInput, setBaseUrlInput] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadModels();
  }, [selectedProvider]);

  const loadModels = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${baseUrl}/models?provider=${selectedProvider}`);
      if (r.ok) {
        const data = await r.json();
        setModels(data.models || []);
      }
    } catch {
      console.error('Failed to load models');
    }
    setLoading(false);
  };

  const handleSave = async () => {
    try {
      if (window.electronAPI?.setModel) {
        await window.electronAPI.setModel({
          provider: selectedProvider,
          model: selectedModel,
          baseUrl: baseUrlInput,
          apiKey: apiKey,
        });
      }
      setModelInfo(selectedModel, selectedProvider);
    } catch (err) {
      console.error('Failed to save model:', err);
    }
  };

  const handleRefresh = () => {
    loadModels();
  };

  return (
    <div className="models-view">
      <div className="models-header">
        <h2 className="models-title">Models</h2>
        <p className="models-desc">Select and manage AI models for this workspace.</p>
      </div>
      <div className="model-modal-body">
        <div className="model-providers-panel">
          <div className="model-providers-panel-title">LLM Provider</div>
          <div className="model-providers-list">
            {providers.map((provider) => {
              const Icon = provider.icon;
              return (
                <button
                  key={provider.id}
                  type="button"
                  className={`model-provider-item ${selectedProvider === provider.id ? 'active' : ''}`}
                  onClick={() => setSelectedProvider(provider.id)}
                >
                  <span className="model-provider-icon">
                    <Icon />
                  </span>
                  {provider.name}
                </button>
              );
            })}
          </div>
        </div>
        <div className="model-models-panel">
          <div className="model-models-panel-header">
            <div>
              <div className="model-models-panel-title">Available Models</div>
              <p className="model-models-prompt">Select a model to use for this workspace.</p>
            </div>
            <button
              type="button"
              className="model-refresh-btn"
              onClick={handleRefresh}
              title="Refresh model list"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
                <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                <path d="M16 21h5v-5" />
              </svg>
            </button>
          </div>

          {selectedProvider !== 'builtin' && (
            <>
              <div className="modal-field model-field-base-url">
                <label className="modal-label" htmlFor="model-base-url">Base URL</label>
                <input
                  type="text"
                  id="model-base-url"
                  className="modal-input"
                  placeholder="Optional – custom endpoint"
                  value={baseUrlInput}
                  onChange={(e) => setBaseUrlInput(e.target.value)}
                />
              </div>
              {selectedProvider !== 'ollama' && (
                <div className="modal-field model-field-api-key">
                  <label className="modal-label" htmlFor="model-api-key">API Key</label>
                  <input
                    type="password"
                    id="model-api-key"
                    className="modal-input"
                    placeholder="Required for cloud providers"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
              )}
            </>
          )}

          <div className="modal-field">
            <label className="modal-label" htmlFor="model-select">Model</label>
            <div className="modal-select-wrapper">
              <select
                id="model-select"
                className="modal-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                <option value="">Select a model...</option>
                {models.map((model) => (
                  <option key={model.id || model.name} value={model.id || model.name}>
                    {model.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
      <div className="models-footer">
        <button type="button" className="btn-modal-primary" onClick={handleSave}>
          Save
        </button>
      </div>
    </div>
  );
}

export default ModelsPage;
