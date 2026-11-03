(function () {
  // ---- filter chips on the blog index
  var chips = [].slice.call(document.querySelectorAll('.chip'));
  if (chips.length) {
    var rows = [].slice.call(document.querySelectorAll('.row'));
    var years = [].slice.call(document.querySelectorAll('.year'));
    var count = document.querySelector('.archive-count');
    var empty = document.querySelector('.empty');
    var notes = [].slice.call(document.querySelectorAll('.series-note'));
    var apply = function (key) {
      var n = 0;
      rows.forEach(function (r) {
        var ok = key === 'all' || r.dataset.tags.split(' ').indexOf(key) > -1;
        r.hidden = !ok; if (ok) n++;
      });
      years.forEach(function (y) { y.hidden = !y.querySelector('.row:not([hidden])'); });
      chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.key === key)); });
      if (count) count.textContent = n + (n === 1 ? ' piece' : ' pieces');
      if (empty) empty.hidden = n > 0;
      notes.forEach(function (x) { x.hidden = x.dataset.key !== key; });
    };
    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        apply(c.dataset.key);
        history.replaceState(null, '', c.dataset.key === 'all' ? location.pathname : '#' + c.dataset.key);
      });
    });
    var h = location.hash.slice(1);
    if (h && chips.some(function (c) { return c.dataset.key === h; })) {
      apply(h);
      var arch = document.querySelector('.archive');
      if (arch) arch.scrollIntoView();
    }
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
