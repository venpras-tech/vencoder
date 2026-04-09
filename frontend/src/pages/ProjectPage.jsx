import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import './ProjectPage.css';

function ProjectPage() {
  const { projectPath, setProjectPath, baseUrl } = useApp();
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [showTemplateDropdown, setShowTemplateDropdown] = useState(false);

  useEffect(() => {
    if (projectPath) {
      loadFileTree();
    }
  }, [projectPath]);

  const loadFileTree = async () => {
    if (!projectPath) return;
    setLoading(true);
    try {
      if (window.electronAPI?.readDirectory) {
        const tree = await window.electronAPI.readDirectory(projectPath);
        setFiles(tree || []);
      }
    } catch {
      console.error('Failed to load file tree');
    }
    setLoading(false);
  };

  const handleBrowseProject = async () => {
    if (window.electronAPI?.openDirectory) {
      const path = await window.electronAPI.openDirectory();
      if (path) {
        setProjectPath(path);
      }
    }
  };

  const handleIndex = async () => {
    if (!projectPath) return;
    setIndexing(true);
    try {
      await fetch(`${baseUrl}/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: projectPath }),
      });
    } catch {
      console.error('Failed to index project');
    }
    setIndexing(false);
  };

  const handleFileClick = async (file) => {
    if (file.isDirectory) return;
    setSelectedFile(file);
    try {
      if (window.electronAPI?.readFile) {
        const content = await window.electronAPI.readFile(file.path);
        setFileContent(content);
      }
    } catch {
      console.error('Failed to read file');
    }
  };

  const handleTemplateSelect = (template) => {
    setShowTemplateDropdown(false);
    // Create project template files
  };

  return (
    <div className="project-view">
      <div className="project-header">
        <div className="project-header-row">
          <label className="project-label">Workspace</label>
          <button
            type="button"
            className="project-path project-path-full"
            onClick={handleBrowseProject}
            title="Click to change project folder"
          >
            <span className="project-path-icon" aria-hidden="true" />
            <span className="project-path-text">
              {projectPath || 'No folder selected'}
            </span>
          </button>
        </div>
        <div className="project-header-row project-header-row-buttons">
          <button
            type="button"
            className="btn-index btn-index-block"
            onClick={handleIndex}
            disabled={!projectPath || indexing}
          >
            {indexing ? 'Indexing...' : 'Index workspace'}
          </button>
          <div className="project-template-wrap">
            <button
              type="button"
              className="btn-index"
              onClick={() => setShowTemplateDropdown(!showTemplateDropdown)}
              disabled={!projectPath}
            >
              + Project template
            </button>
            {showTemplateDropdown && (
              <div className="project-template-dropdown">
                <button type="button" className="project-template-opt" onClick={() => handleTemplateSelect('python')}>
                  Python
                </button>
                <button type="button" className="project-template-opt" onClick={() => handleTemplateSelect('react')}>
                  React
                </button>
                <button type="button" className="project-template-opt" onClick={() => handleTemplateSelect('node')}>
                  Node.js
                </button>
                <button type="button" className="project-template-opt" onClick={() => handleTemplateSelect('rust')}>
                  Rust
                </button>
              </div>
            )}
          </div>
          <button type="button" className="btn-index" onClick={loadFileTree} disabled={!projectPath}>
            Refresh
          </button>
        </div>
      </div>
      <div className="project-explorer">
        <div className="project-tree-panel">
          <div className="project-tree-header">Files</div>
          <div className="project-tree">
            {loading ? (
              <div className="project-tree-loading">Loading...</div>
            ) : files.length === 0 ? (
              <div className="project-tree-loading">No files</div>
            ) : (
              <FileTree files={files} onFileClick={handleFileClick} selectedFile={selectedFile} />
            )}
          </div>
        </div>
        <div className="project-editor-panel">
          {selectedFile ? (
            <div className="project-editor-container">
              <div className="project-editor-header">
                <span className="project-editor-filename">{selectedFile.name}</span>
              </div>
              <div className="project-editor-scroll">
                <pre className="project-editor-code">
                  <code>{fileContent}</code>
                </pre>
              </div>
            </div>
          ) : (
            <div className="project-editor-placeholder">Select a file to view</div>
          )}
        </div>
      </div>
    </div>
  );
}

function FileTree({ files, onFileClick, selectedFile, depth = 0 }) {
  return (
    <div className="project-tree-children" style={{ paddingLeft: depth > 0 ? 12 : 0 }}>
      {files.map((file) => (
        <div key={file.path}>
          <div
            className={`project-tree-item ${selectedFile?.path === file.path ? 'selected' : ''}`}
            onClick={() => onFileClick(file)}
          >
            <span className="project-tree-item-icon">
              {file.isDirectory ? '📁' : '📄'}
            </span>
            <span className="project-tree-item-name">{file.name}</span>
          </div>
          {file.isDirectory && file.children && (
            <FileTree
              files={file.children}
              onFileClick={onFileClick}
              selectedFile={selectedFile}
              depth={depth + 1}
            />
          )}
        </div>
      ))}
    </div>
  );
}

export default ProjectPage;
