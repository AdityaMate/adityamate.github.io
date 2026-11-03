(function () {
  // ---- menu on the blog index: Featured (cards) | All | topics | series (list)
  var chips = [].slice.call(document.querySelectorAll('.chip'));
  var browse = document.querySelector('.browse');
  if (chips.length && browse) {
    var def = browse.dataset.default || 'all';
    var rows = [].slice.call(document.querySelectorAll('.row'));
    var years = [].slice.call(document.querySelectorAll('.year'));
    var count = document.querySelector('.archive-count');
    var empty = document.querySelector('.empty');
    var notes = [].slice.call(document.querySelectorAll('.series-note'));
    var pFeat = document.querySelector('.panel-featured');
    var pList = document.querySelector('.panel-list');
    var apply = function (key) {
      var featured = key === 'featured';
      if (pFeat) pFeat.hidden = !featured;
      if (pList) pList.hidden = featured;
      var n = 0;
      rows.forEach(function (r) {
        var ok = key === 'all' || featured || r.dataset.tags.split(' ').indexOf(key) > -1;
        r.hidden = !ok; if (ok && !featured) n++;
      });
      years.forEach(function (y) { y.hidden = !y.querySelector('.row:not([hidden])'); });
      chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.key === key)); });
      notes.forEach(function (x) { x.hidden = x.dataset.key !== key; });
      if (count) count.textContent = featured ? '' : n + (n === 1 ? ' piece' : ' pieces');
      if (empty) empty.hidden = featured || n > 0;
    };
    var keys = chips.map(function (c) { return c.dataset.key; });
    var setHash = function (key) { history.replaceState(null, '', key === def ? location.pathname : '#' + key); };
    chips.forEach(function (c) {
      c.addEventListener('click', function () { apply(c.dataset.key); setHash(c.dataset.key); });
    });
    notes.forEach(function (n) {
      var x = n.querySelector('.note-clear');
      if (x) x.addEventListener('click', function () { apply('all'); setHash('all'); });
    });
    var route = function (scroll) {
      var h = location.hash.slice(1);
      if (!h) { apply(def); return; }
      if (keys.indexOf(h) > -1) {
        apply(h);
        if (scroll) browse.scrollIntoView();
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
