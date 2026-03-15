(function() {
  var origFetch = window.fetch;
  window.fetch = function(url, opts) {
    var urlStr = typeof url === 'string' ? url : (url && url.url) || '';
    if (urlStr.indexOf('/chat') !== -1 && (opts && opts.method) === 'POST') {
      return origFetch.apply(this, arguments).then(function(res) {
        if (!res.body) return res;
        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var stream = new ReadableStream({
          start: function(controller) {
            function pump() {
              return reader.read().then(function(r) {
                if (r.done) {
                  controller.close();
                  return;
                }
                var chunk = decoder.decode(r.value, { stream: true });
                buffer += chunk;
                var lines = buffer.split('\n');
                buffer = lines.pop() || '';
                lines.forEach(function(line) {
                  var s = line.trim();
                  if (!s) return;
                  if (s.indexOf('data:') === 0) s = s.slice(5).trim();
                  try {
                    var data = JSON.parse(s);
                    var el = document.getElementById('activity');
                    if (!el) return;
                    if (data.type === 'log' && data.message) {
                      var item = document.createElement('div');
                      item.className = 'activity-item activity-log';
                      var label = document.createElement('span');
                      label.className = 'activity-label';
                      label.textContent = (data.level || 'INFO') + ':';
                      var body = document.createElement('span');
                      body.className = 'activity-body';
                      body.textContent = data.message;
                      item.appendChild(label);
                      item.appendChild(body);
                      el.appendChild(item);
                      el.scrollTop = el.scrollHeight;
                    } else if (data.type === 'response_meta' && data.tokens != null) {
                      var meta = document.createElement('div');
                      meta.className = 'activity-item activity-log';
                      var metaLabel = document.createElement('span');
                      metaLabel.className = 'activity-label';
                      metaLabel.textContent = 'Done:';
                      var metaBody = document.createElement('span');
                      metaBody.className = 'activity-body';
                      metaBody.textContent = data.tokens + ' tokens, ' + (data.duration_ms || 0) + 'ms, ' + (data.tok_per_sec || 0) + ' tok/s';
                      meta.appendChild(metaLabel);
                      meta.appendChild(metaBody);
                      el.appendChild(meta);
                      el.scrollTop = el.scrollHeight;
                    }
                  } catch (_) {}
                });
                controller.enqueue(r.value);
                return pump();
              });
            }
            pump();
          }
        });
        return new Response(stream, { headers: res.headers, status: res.status });
      });
    }
    return origFetch.apply(this, arguments);
  };
})();
