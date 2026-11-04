(function () {
  // ---- filters for the "All writing" list on the blog index (the Pinned and Series rows above never change)
  var chips = [].slice.call(document.querySelectorAll('.chip'));
  var archive = document.querySelector('.archive');
  if (chips.length && archive) {
    var rows = [].slice.call(document.querySelectorAll('.row'));
    var years = [].slice.call(document.querySelectorAll('.year'));
    var count = document.querySelector('.archive-count');
    var empty = document.querySelector('.empty');
    var notes = [].slice.call(document.querySelectorAll('.series-hero'));
    var apply = function (key) {
      var n = 0;
      rows.forEach(function (r) {
        var ok = key === 'all' || r.dataset.tags.split(' ').indexOf(key) > -1;
        r.hidden = !ok; if (ok) n++;
      });
      years.forEach(function (y) { y.hidden = !y.querySelector('.row:not([hidden])'); });
      chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.key === key)); });
      notes.forEach(function (x) { x.hidden = x.dataset.key !== key; });
      if (count) count.textContent = n + (n === 1 ? ' piece' : ' pieces');
      if (empty) empty.hidden = n > 0;
    };
    var keys = chips.map(function (c) { return c.dataset.key; });
    var setHash = function (key) { history.replaceState(null, '', key === 'all' ? location.pathname : '#' + key); };
    chips.forEach(function (c) {
      c.addEventListener('click', function (e) { apply(c.dataset.key); setHash(c.dataset.key); if (e.detail > 0) c.blur(); });
    });
    notes.forEach(function (n) {
      var x = n.querySelector('.note-clear');
      if (x) x.addEventListener('click', function () { apply('all'); setHash('all'); });
    });
    var route = function (scroll) {
      var h = location.hash.slice(1);
      if (!h) { apply('all'); return; }
      if (keys.indexOf(h) > -1) {
        apply(h);
        if (scroll) archive.scrollIntoView();
      }
    };
    window.addEventListener('hashchange', function () { route(true); });
    route(true);
  }

  // ---- click any photo in a post to see it full size
  var imgs = document.querySelectorAll('.prose figure img');
  if (!imgs.length) return;
  var lb = document.createElement('div');
  lb.className = 'lightbox'; lb.hidden = true;
  lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true'); lb.setAttribute('aria-label', 'Photo');
  lb.innerHTML = '<button class="lb-close" aria-label="Close photo">×</button><img alt=""><p class="lb-cap"></p>';
  document.body.appendChild(lb);
  var last = null;
  var close = function () { lb.hidden = true; document.body.style.overflow = ''; if (last) last.focus(); };
  lb.addEventListener('click', function (e) { if (e.target === lb || e.target.classList.contains('lb-close')) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !lb.hidden) close(); });
  [].forEach.call(imgs, function (img) {
    img.tabIndex = 0; img.setAttribute('role', 'button');
    var open = function () {
      last = img;
      var big = lb.querySelector('img'); big.src = img.currentSrc || img.src; big.alt = img.alt;
      var cap = img.closest('figure').querySelector('figcaption');
      lb.querySelector('.lb-cap').textContent = cap ? cap.textContent : '';
      lb.hidden = false; document.body.style.overflow = 'hidden';
      lb.querySelector('.lb-close').focus();
    };
    img.addEventListener('click', open);
    img.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
  });
})();
