(function() {
  var treeCache = null;
  var origFetch = window.fetch;
  window.fetch = function(url, opts) {
    var urlStr = typeof url === 'string' ? url : (url && url.url) || '';
    if (urlStr.indexOf('/files/tree') !== -1) {
      var forceRefresh = urlStr.indexOf('refresh=true') !== -1;
      if (!forceRefresh && treeCache) {
        return Promise.resolve(new Response(JSON.stringify(treeCache), {
          headers: { 'Content-Type': 'application/json' }
        }));
      }
      return origFetch.apply(this, arguments).then(function(r) {
        var clone = r.clone();
        clone.json().then(function(data) { treeCache = data; }).catch(function() {});
        return r;
      });
    }
    return origFetch.apply(this, arguments);
  };
  if (window.electronAPI && window.electronAPI.onProjectPath) {
    window.electronAPI.onProjectPath(function() { treeCache = null; });
  }
})();
