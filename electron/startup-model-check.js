(function() {
  var api = window.electronAPI || (window.__TAURI__ && window.__TAURI__.core ? null : null);
  if (!api || !api.getBackendUrl) return;

  function runProbe() {
    api.getBackendUrl().then(function(base) {
      if (!base) return;
      var url = base.replace(/\/$/, '') + '/probe/available';
      fetch(url, { signal: AbortSignal.timeout(5000) }).then(function(r) {
        return r.ok ? r.json() : Promise.reject(new Error('probe failed'));
      }).then(function(data) {
        window.__probeAvailable = data;
      }).catch(function() {});
    }).catch(function() {});
  }

  function waitForBackend() {
    var tries = 0;
    var maxTries = 60;
    function attempt() {
      api.getBackendUrl().then(function(base) {
        if (!base) {
          if (++tries < maxTries) setTimeout(attempt, 500);
          return;
        }
        fetch(base.replace(/\/$/, '') + '/health', { signal: AbortSignal.timeout(3000) }).then(function(r) {
          if (r.ok) runProbe();
        }).catch(function() {
          if (++tries < maxTries) setTimeout(attempt, 500);
        });
      }).catch(function() {
        if (++tries < maxTries) setTimeout(attempt, 500);
      });
    }
    setTimeout(attempt, 1500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForBackend);
  } else {
    waitForBackend();
  }
})();
