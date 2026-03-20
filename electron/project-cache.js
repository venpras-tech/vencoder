(function() {
  var treeCache = null;
  var origFetch = window.fetch;
  function makeTreeResponse(data) {
    return Promise.resolve(new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' }
    }));
  }
  function getPathFromUrl(urlStr) {
    try {
      var idx = urlStr.indexOf('?');
      if (idx === -1) return null;
      var qs = urlStr.slice(idx + 1);
      var params = qs.split('&');
      for (var i = 0; i < params.length; i++) {
        var p = params[i];
        if (p.indexOf('path=') === 0) {
          return decodeURIComponent(p.slice(5).replace(/\+/g, ' '));
        }
      }
    } catch (e) {}
    return null;
  }

  window.fetch = function(url, opts) {
    var urlStr = typeof url === 'string' ? url : (url && url.url) || '';
    if (urlStr.indexOf('/files/tree') !== -1) {
      var forceRefresh = urlStr.indexOf('refresh=true') !== -1;
      if (!forceRefresh && treeCache) {
        return makeTreeResponse(treeCache);
      }
      var api = window.electronAPI;
      if (api && api.getFileTree && !forceRefresh) {
        var urlArg = url;
        var optsArg = opts;
        return api.getFileTree().then(function(data) {
          if (data && data.tree) treeCache = data;
          return makeTreeResponse(data || { tree: [] });
        }).catch(function() {
          return origFetch(urlArg, optsArg).then(function(r) {
            var clone = r.clone();
            clone.json().then(function(d) { treeCache = d; }).catch(function() {});
            return r;
          });
        });
      }
      return origFetch.apply(this, arguments).then(function(r) {
        var clone = r.clone();
        clone.json().then(function(data) { treeCache = data; }).catch(function() {});
        return r;
      });
    }
    if (urlStr.indexOf('/files/content') !== -1) {
      var api = window.electronAPI;
      var relPath = getPathFromUrl(urlStr);
      if (api && api.getFileContent && relPath) {
        return api.getFileContent(relPath).then(function(data) {
          if (data) return makeTreeResponse(data);
          return origFetch(url, opts);
        }).catch(function() {
          return origFetch(url, opts);
        });
      }
    }
    return origFetch.apply(this, arguments);
  };
  if (window.electronAPI && window.electronAPI.onProjectPath) {
    window.electronAPI.onProjectPath(function() { treeCache = null; });
  }

  function prefetchTree() {
    var api = window.electronAPI || (window.__TAURI__ && window.__TAURI__.core ? null : null);
    if (!api) return;
    if (api.getFileTree) {
      api.getFileTree().then(function(data) {
        if (data && data.tree) treeCache = data;
      }).catch(function() {});
      return;
    }
    if (!api.getBackendUrl) return;
    api.getBackendUrl().then(function(base) {
      if (!base) return;
      var url = (base.replace(/\/$/, '') + '/files/tree');
      origFetch(url).then(function(r) {
        if (r.ok) return r.json();
        throw new Error('fetch failed');
      }).then(function(data) {
        if (data && data.tree) treeCache = data;
      }).catch(function() {});
    }).catch(function() {});
  }

  function schedulePrefetch() {
    if (window._projectPrefetchScheduled) return;
    window._projectPrefetchScheduled = true;
    var api = window.electronAPI || (window.__TAURI__ && window.__TAURI__.core ? null : null);
    if (api && api.getFileTree) {
      setTimeout(function() { prefetchTree(); window._projectPrefetchScheduled = false; }, 500);
      return;
    }
    var tries = 0;
    var maxTries = 12;
    function tryPrefetch() {
      if (!api || !api.getBackendUrl) {
        window._projectPrefetchScheduled = false;
        return;
      }
      api.getBackendUrl().then(function(base) {
        if (!base) return Promise.resolve(false);
        return origFetch(base.replace(/\/$/, '') + '/health').then(function(r) { return r.ok; }).catch(function() { return false; });
      }).then(function(ready) {
        if (ready) {
          prefetchTree();
        } else if (++tries < maxTries) {
          setTimeout(tryPrefetch, 1500);
          return;
        }
        window._projectPrefetchScheduled = false;
      }).catch(function() {
        if (++tries < maxTries) setTimeout(tryPrefetch, 1500);
        else window._projectPrefetchScheduled = false;
      });
    }
    setTimeout(tryPrefetch, 2000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedulePrefetch);
  } else {
    schedulePrefetch();
  }

  if (window.electronAPI && window.electronAPI.onProjectPath) {
    window.electronAPI.onProjectPath(function() {
      schedulePrefetch();
    });
  }
})();
