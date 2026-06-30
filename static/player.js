(function () {
  'use strict';

  // ── DOM refs ──────────────────────────────────────────────────
  var bar     = document.getElementById('player-bar');
  var audio   = document.getElementById('player-audio');
  var playBtn = document.getElementById('player-play');
  var prevBtn = document.getElementById('player-prev');
  var nextBtn = document.getElementById('player-next');
  var seekEl  = document.getElementById('player-seek');
  var volEl   = document.getElementById('player-vol');
  var timeEl  = document.getElementById('player-time');
  var durEl   = document.getElementById('player-dur');
  var nameEl  = document.getElementById('player-track-name');

  // ── Player state ──────────────────────────────────────────────
  var tracks  = [];
  var current = 0;
  var seeking = false;

  function fmt(sec) {
    sec = Math.floor(sec || 0);
    return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2);
  }

  function randomTrack() {
    if (tracks.length <= 1) return 0;
    var idx;
    do { idx = Math.floor(Math.random() * tracks.length); } while (idx === current);
    return idx;
  }

  function loadTrack(idx, autoplay) {
    current = ((idx % tracks.length) + tracks.length) % tracks.length;
    var t = tracks[current];
    audio.src = t.url;
    nameEl.textContent = t.name;
    seekEl.value = 0;
    timeEl.textContent = '0:00';
    durEl.textContent  = '0:00';
    if (autoplay) audio.play().catch(function () {});
    saveState();
  }

  function updatePlayBtn() {
    playBtn.textContent = audio.paused ? '▶' : '⏸';
    // keep optical nudge for ▶ but not ⏸
    playBtn.style.paddingLeft = audio.paused ? '2px' : '0';
  }

  // ── Audio events ──────────────────────────────────────────────
  playBtn.addEventListener('click', function () {
    if (!tracks.length) return;
    if (!audio.src || audio.src === window.location.href) {
      loadTrack(0, true);
      return;
    }
    if (audio.paused) {
      audio.play().catch(function () {});
    } else {
      audio.pause();
    }
  });

  prevBtn.addEventListener('click', function () {
    if (tracks.length) loadTrack(current - 1, !audio.paused);
  });

  nextBtn.addEventListener('click', function () {
    if (tracks.length) loadTrack(current + 1, !audio.paused);
  });

  audio.addEventListener('play',  updatePlayBtn);
  audio.addEventListener('pause', updatePlayBtn);
  audio.addEventListener('ended', function () { loadTrack(current + 1, true); });

  audio.addEventListener('timeupdate', function () {
    if (seeking || !audio.duration) return;
    seekEl.value = audio.currentTime / audio.duration * 100;
    timeEl.textContent = fmt(audio.currentTime);
    durEl.textContent  = fmt(audio.duration);
  });

  seekEl.addEventListener('mousedown',  function () { seeking = true; });
  seekEl.addEventListener('touchstart', function () { seeking = true; }, { passive: true });

  seekEl.addEventListener('input', function () {
    if (audio.duration) timeEl.textContent = fmt(audio.duration * seekEl.value / 100);
  });

  seekEl.addEventListener('change', function () {
    seeking = false;
    if (audio.duration) audio.currentTime = audio.duration * seekEl.value / 100;
    saveState();
  });

  volEl.addEventListener('input', function () {
    audio.volume = parseFloat(volEl.value);
    saveState();
  });

  // ── State persistence (survives POST-redirect full reloads) ───
  var STATE_KEY = 'mm_player';

  function saveState() {
    try {
      localStorage.setItem(STATE_KEY, JSON.stringify({
        idx:     current,
        time:    audio.currentTime,
        playing: !audio.paused,
        vol:     audio.volume,
      }));
    } catch (_) {}
  }

  setInterval(saveState, 4000);
  window.addEventListener('beforeunload', saveState);

  function restoreState(s) {
    if (!s || !tracks.length) return;
    audio.volume = (s.vol !== undefined) ? s.vol : 0.7;
    volEl.value  = audio.volume;

    if (s.playing) {
      // Resume exactly where the user left off
      current = Math.min(s.idx || 0, tracks.length - 1);
      var t = tracks[current];
      audio.src = t.url;
      nameEl.textContent = t.name;
      if (s.time && s.time > 0) {
        audio.addEventListener('loadedmetadata', function onMeta() {
          audio.removeEventListener('loadedmetadata', onMeta);
          audio.currentTime = s.time;
          audio.play().catch(function () {});
        });
      } else {
        audio.play().catch(function () {});
      }
    } else {
      // Music was paused — shuffle to a fresh track
      loadTrack(randomTrack(), false);
    }
  }

  // ── AJAX navigation ───────────────────────────────────────────
  // Intercept same-origin <a> clicks so the player bar never unmounts.
  // POST forms (save session, settings, etc.) do full-page nav as normal —
  // the beforeunload handler saves state so restoreState() picks it up.

  var PAGE_SCRIPT = 'data-page-script';

  // Paths that must do a full-page load (file downloads, SSE, static assets)
  var SKIP_RE = /^\/(static|uploads|assets|export)\//;

  function navigate(url, push) {
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) {
        if (!r.ok) { location.href = url; return null; }
        return r.text();
      })
      .then(function (html) {
        if (!html) return;
        var doc = new DOMParser().parseFromString(html, 'text/html');

        // Swap nav (updates active link highlight) and main (page content)
        var newNav  = doc.querySelector('nav');
        var newMain = doc.querySelector('main');
        if (!newNav || !newMain) { location.href = url; return; }
        document.querySelector('nav').innerHTML  = newNav.innerHTML;
        document.querySelector('main').innerHTML = newMain.innerHTML;

        document.title = doc.title;
        if (push) history.pushState({ url: url }, doc.title, url);
        window.scrollTo(0, 0);

        // Remove inline scripts injected by a previous AJAX nav
        document.querySelectorAll('[' + PAGE_SCRIPT + ']').forEach(function (s) {
          s.remove();
        });

        // Re-run the new page's inline <script> blocks ({% block scripts %})
        doc.querySelectorAll('body script:not([src])').forEach(function (s) {
          var ns = document.createElement('script');
          ns.setAttribute(PAGE_SCRIPT, '');
          ns.textContent = s.textContent;
          document.body.appendChild(ns);
        });

        if (audio.paused) loadTrack(randomTrack(), false);
        saveState();
      })
      .catch(function () { location.href = url; });
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href]');
    if (!a || e.defaultPrevented) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== '_self') return;
    if (a.download) return;

    var href = a.href;
    if (!href.startsWith(location.origin + '/')) return;   // external link

    var path = href.slice(location.origin.length);
    if (SKIP_RE.test(path) || path.charAt(0) === '#') return;

    // Already on this page
    if (path === location.pathname + location.search) return;

    e.preventDefault();
    navigate(href, true);
  }, true);

  window.addEventListener('popstate', function () {
    navigate(location.href, false);
  });

  // ── Bootstrap ─────────────────────────────────────────────────
  fetch('/api/tracks')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      tracks = (data.tracks || []).map(function (f) {
        // "01 - Ellinia Forest.mp3" → "01   Ellinia Forest"
        var name = f.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
        return { name: name, url: '/assets/' + encodeURIComponent(f) };
      });

      if (!tracks.length) return;

      bar.removeAttribute('hidden');
      document.documentElement.style.setProperty('--player-h', '64px');

      try {
        var saved = JSON.parse(localStorage.getItem(STATE_KEY) || 'null');
        if (saved) {
          restoreState(saved);
        } else {
          loadTrack(randomTrack(), false);
        }
      } catch (_) {
        loadTrack(randomTrack(), false);
      }
    })
    .catch(function () { /* assets/ empty or unreachable — player stays hidden */ });

}());
