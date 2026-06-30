// Drop row management (confirm.html)
function addDropRow() {
  const container = document.getElementById('drops-container');
  const row = document.createElement('div');
  row.className = 'drop-row';
  row.innerHTML =
    '<input type="text" name="item_name[]" placeholder="Item name" autocomplete="off">' +
    '<input type="number" name="quantity[]" placeholder="Qty" min="0">' +
    '<button type="button" class="btn btn-secondary" onclick="removeDropRow(this)">Remove</button>';
  container.appendChild(row);
  row.querySelector('input').focus();
}

function removeDropRow(btn) {
  btn.closest('.drop-row').remove();
}

// Shared Ollama model pull — used on both /models and /settings
function pullModel(name, idx) {
  const btn      = document.getElementById('pull-btn-' + idx);
  const statusEl = document.getElementById('pull-progress-' + idx);

  btn.disabled           = true;
  btn.textContent        = 'Pulling…';
  statusEl.style.display = 'block';
  statusEl.innerHTML     = '<p class="text-muted text-sm">Starting download…</p>';

  const source = new EventSource('/models/pull/' + encodeURIComponent(name));

  source.onmessage = function(e) {
    let data;
    try { data = JSON.parse(e.data); } catch(_) { return; }

    if (data.done) {
      source.close();
      statusEl.innerHTML = '<p style="color:var(--success)">Download complete! Reloading…</p>';
      setTimeout(function() { location.reload(); }, 1500);
      return;
    }

    if (data.error) {
      source.close();
      statusEl.innerHTML = '<p style="color:var(--error)">Error: ' + data.error + '</p>';
      btn.disabled    = false;
      btn.textContent = 'Retry';
      return;
    }

    var msg = data.status || 'Working…';
    var bar = '';
    if (data.total && data.completed) {
      var pct = Math.round(data.completed / data.total * 100);
      msg = data.status + ': ' + pct + '%';
      bar = '<div class="progress-bar"><div class="progress-fill" style="width:' + pct + '%"></div></div>';
    }
    statusEl.innerHTML = '<p class="text-muted text-sm">' + msg + '</p>' + bar;
  };

  source.onerror = function() {
    source.close();
    statusEl.innerHTML = '<p style="color:var(--error)">Connection lost.</p>';
    btn.disabled    = false;
    btn.textContent = 'Retry';
  };
}
