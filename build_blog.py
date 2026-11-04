#!/usr/bin/env python3
"""Builds the blog from Markdown files in blog-src/posts/ into blog/.

    python3 build_blog.py           # build
    python3 build_blog.py --serve   # build, then preview at http://localhost:8000/blog/

Writing a new post: add blog-src/posts/YYYY-MM-DD-some-slug.md with front matter, e.g.

    ---
    title: My new post
    date: 2026-11-10
    format: essay            # essay | note | diary
    topics: [Cricket]        # any of the TOPICS below
    series: crease           # optional, a key from SERIES below
    series_part: 2           # optional, its position in the series
    featured: 1              # optional, 1-3 = position in the Recommended row
    cover: /blog/img/my-photo.jpg   # optional card image
    hook: One or two sentences that make people want to click.
    excerpt: **Mar 2022:** Optional text for the All writing list (markdown); ends with Read more...  Falls back to hook.
    draft: true              # optional, keeps it unpublished
    ---

Then run the build and commit everything. Needs: pip3 install markdown
"""
import datetime, html, math, pathlib, re, shutil, sys

try:
    import markdown
except ImportError:
    sys.exit("This needs the 'markdown' package:  pip3 install markdown")

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / 'blog-src'
OUT = ROOT / 'blog'
SITE = 'https://adityamate.github.io'

# ---------------------------------------------------------------- settings
# While True: blog pages get <meta name="robots" content="noindex"> and the blog
# URLs are left out of sitemap.xml. Set to False when you're ready to go public
# (and point the homepage "Blog" link back at blog/).
UNLISTED = True

BLOG = {
    'title': 'A Slice of Life',
    'subtitle': '',   # small italic line under the title; '' to hide
    'intro': ('Welcome to my non-technical, non-serious personal blog! This is where I post curious '
              'stories, armchair thoughts, travel accounts or just some random slice-of-my-life '
              'narrations from my personal diary.'),
    'feedback': 'https://docs.google.com/forms/d/e/1FAIpQLSeq8BZfUlsnZ-JsNJCu9C_hOrYUOk3JcfokS55Jc4S9epCujA/viewform?usp=sf_link',
    # dashed "Coming soon" boxes at the bottom of the page; add or remove titles freely
    'in_the_works': [
        'First impressions of the City of Angels',
        'Snapshots enroute the Ph.D.',
        'Pandemic year in the rear-view mirror',
        'Working at Mountain View and Yorktown Heights... virtually',
        'NYC: The east coast way of life',
        'The Sklarzhaus, Vermont',
    ],
}
SERIES = {
    'crease': {
        'title': 'Tales from the Crease',
        'cover': '/blog/img/crease-trophy.jpg',   # optional; defaults to the first story's cover
        'spine': '#2E4372',                              # book spine colour
        'style': 'pitch',                                # title plate drawn as a sketched cricket pitch
        'blurb': ('Stories from matches I’ve played: the collapses, the comebacks, '
                  'and the baseball player who out-batted all of us.'),
        'more_coming': 'More match stories on the way',
    },
    'diary': {
        'title': 'Pages from My Diary',
        'blurb': ('Unpolished pages from my diary: the trips, reunions and ordinary days '
                  'I would happily freeze in time.'),
        'more_coming': 'More pages on the way',
        'spine': '#7A5A1E',
        'cover': '/blog/img/pune-trip-02.jpg',
        'style': 'snapshot',          # taped snapshot on a leather cover (default is a full-photo cover)
        'caption': 'Pune, Jan 2020',  # handwritten caption under the snapshot
        'unit': ('page', 'pages'),
    },
}
# formats whose filter chip is left out (a Stories chip next to All is just confusing; a series covers diary)
NO_FORMAT_CHIP = {'diary', 'essay'}
# keys are what you write in front matter (format: essay); the labels are what readers see
FORMATS = {'essay': ('Story', 'Stories'), 'note': ('Note', 'Notes'), 'diary': ('Diary', 'Diary')}
TOPICS = ['Cricket', 'Travel', 'Work & Study', 'Life']
# -------------------------------------------------------------------------

# short content hash appended to blog.css / blog.js links so browsers never reuse a stale copy after a deploy
import hashlib
ASSET_V = hashlib.md5(b''.join((SRC / a).read_bytes() for a in ('blog.css', 'blog.js'))).hexdigest()[:8]

esc = lambda s: html.escape(str(s), quote=True)
slugify = lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def parse_post(path):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', text, re.S)
    if not m:
        sys.exit(f'{path.name}: missing --- front matter ---')
    meta = {}
    for line in m.group(1).splitlines():
        line = re.sub(r'\s+#\s.*$', '', line)  # trailing comments
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        k, _, v = line.partition(':')
        k, v = k.strip(), v.strip()
        if v.startswith('[') and v.endswith(']'):
            v = [x.strip().strip('"\'') for x in v[1:-1].split(',') if x.strip()]
        elif v.lower() in ('true', 'false'):
            v = v.lower() == 'true'
        elif re.fullmatch(r'\d+', v):
            v = int(v)
        elif len(v) > 1 and v[0] == v[-1] and v[0] in '"\'':
            v = v[1:-1]
        meta[k] = v
    for req in ('title', 'date'):
        if req not in meta:
            sys.exit(f'{path.name}: front matter needs "{req}"')
    d = datetime.date.fromisoformat(str(meta['date']))
    p = {
        'title': meta['title'],
        'date': d,
        'date_label': meta.get('date_label') or d.strftime('%B %Y'),
        'slug': meta.get('slug') or re.sub(r'^\d{4}-\d{2}-\d{2}-', '', path.stem),
        'format': meta.get('format', 'essay'),
        'topics': meta.get('topics', []) if isinstance(meta.get('topics', []), list) else [meta['topics']],
        'series': meta.get('series'),
        'series_part': meta.get('series_part'),
        'featured': meta.get('featured') if isinstance(meta.get('featured'), int) and meta.get('featured') is not True else (1 if meta.get('featured') is True else None),
        'cover': meta.get('cover'),
        'hook': meta.get('hook', ''),
        'excerpt': meta.get('excerpt', ''),
        'draft': meta.get('draft', False),
        'body': m.group(2),
    }
    if p['format'] not in FORMATS:
        sys.exit(f'{path.name}: format must be one of {list(FORMATS)}')
    for t in p['topics']:
        if t not in TOPICS:
            sys.exit(f'{path.name}: unknown topic "{t}" (add it to TOPICS in build_blog.py)')
    if p['series'] and p['series'] not in SERIES:
        sys.exit(f'{path.name}: unknown series "{p["series"]}" (add it to SERIES in build_blog.py)')
    words = len(re.findall(r'\w+', re.sub(r'!\[.*?\]\(.*?\)', '', p['body'])))
    p['minutes'] = max(1, math.ceil(words / 230))
    return p


def local(src, rel):
    """Turn /blog/... paths into paths relative to the page."""
    return rel + src[len('/blog/'):] if src.startswith('/blog/') else src


USED_THUMBS = set()


def thumb_for(p, rel):
    """Small 3:2 thumbnail for the 'All writing' rows: the post's cover, else its first body image.
    Written to blog/img/thumbs/ (falls back to the full image if Pillow isn't installed)."""
    src = p['cover']
    if not src:
        m = re.search(r'!\[.*?\]\((/blog/img/[^)\s]+)\)', p['body'])
        src = m.group(1) if m else None
    if not src or not src.startswith('/blog/img/'):
        return None
    try:
        from PIL import Image, ImageOps
        origin = ROOT / src.lstrip('/')
        dest = OUT / 'img' / 'thumbs' / (pathlib.Path(src).stem + '.jpg')
        if not dest.exists() or dest.stat().st_mtime < origin.stat().st_mtime:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(origin) as im:
                im = ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'), (360, 240), Image.LANCZOS)
                im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
        USED_THUMBS.add(dest.name)
        return f'{rel}img/thumbs/{dest.name}'
    except ImportError:
        return local(src, rel)


def inline_md(s):
    return re.sub(r'^<p>|</p>$', '', markdown.markdown(s).strip())


IMG_RE = re.compile(r'^!\[(.*?)\]\((\S+?)\)$')
CAP_RE = re.compile(r'^\*[^*\s].*\*$|^\*[^*\s]\*$', re.S)


def render_body(p, rel):
    blocks = [b.strip() for b in re.split(r'\n\s*\n', p['body'].strip()) if b.strip()]
    out, gallery, i = [], [], 0

    def flush():
        if len(gallery) == 1:
            out.append(gallery[0])
        elif gallery:
            out.append(f'<div class="gallery g{min(len(gallery), 3)}">' + ''.join(gallery) + '</div>')
        gallery.clear()

    while i < len(blocks):
        m = IMG_RE.match(blocks[i])
        if m:
            alt, src = m.groups()
            cap = ''
            if i + 1 < len(blocks) and CAP_RE.match(blocks[i + 1]):
                cap = blocks[i + 1][1:-1].strip()
                i += 1
            alt = alt or re.sub(r'[*_]', '', cap) or f'Photo from “{p["title"]}”'
            fc = f'<figcaption>{inline_md(cap)}</figcaption>' if cap else ''
            gallery.append(f'<figure><img src="{esc(local(src, rel))}" alt="{esc(alt)}" loading="lazy" decoding="async">{fc}</figure>')
        else:
            flush()
            out.append(blocks[i])
        i += 1
    flush()
    return markdown.markdown('\n\n'.join(out), extensions=['extra', 'smarty'])


# ------------------------------------------------------------- templates
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500'
         '&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">')


def page(*, rel, title, desc, url, image, body, og_type='article'):
    img = f'{SITE}{image}' if image and image.startswith('/') else f'{SITE}/portrait.jpg'
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<meta name="robots" content="noindex">' if UNLISTED else ''}
<link rel="canonical" href="{SITE}{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{SITE}{url}">
<meta property="og:site_name" content="Aditya Mate">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{esc(BLOG['title'])}" href="{SITE}/blog/feed.xml">
{FONTS}
<link rel="stylesheet" href="{rel}blog.css?v={ASSET_V}">
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="masthead">
  <a class="brand" href="{rel}../">Aditya Mate</a>
  <nav class="nav" aria-label="Site">
    <a href="{rel}../">About</a>
    <a href="{rel}../publications.html">Publications</a>
    <a href="{rel}../CV_AdityaMate_full.pdf">CV</a>
    <a href="{rel}" aria-current="page">Writing</a>
  </nav>
</header>
{body}
<footer>
  <span>Aditya Mate · Cambridge, MA</span>
  <span><a href="{BLOG['feedback']}" target="_blank" rel="noopener">Anonymous feedback</a> · <a href="{rel}feed.xml">RSS</a></span>
</footer>
<script src="{rel}blog.js?v={ASSET_V}" defer></script>
</body>
</html>
'''


def fmt_badge(p):
    return f'<span class="fmt fmt-{p["format"]}">{FORMATS[p["format"]][0]}</span>'


def card(p, rel, cls=''):
    img = (f'<div class="card-img"><img src="{esc(local(p["cover"], rel))}" alt="" loading="lazy" decoding="async"></div>'
           if p['cover'] else '')
    return f'''<a class="card {cls}{'' if p['cover'] else ' no-img'}" href="{rel}{p['slug']}/">
  {img}<div class="card-body">
    <p class="kicker">{fmt_badge(p)}<span>{esc(p['date_label'])}</span></p>
    <h3>{esc(p['title'])}</h3>
    <p class="hook">{esc(p['hook'])}</p>
    <p class="readtime">{p['minutes']} min read →</p>
  </div>
</a>'''


def series_posts(posts, key):
    return sorted([q for q in posts if q['series'] == key],
                  key=lambda q: (q['series_part'] or 999, q['date']))


def series_list(posts, key, rel, current=None):
    items = []
    for n, q in enumerate(series_posts(posts, key), 1):
        here = ' class="here"' if current is q else ''
        mark = '<span class="you">You’re here</span>' if current is q else f'<span class="d">{esc(q["date_label"])}</span>'
        items.append(f'<li{here}><a href="{rel}{q["slug"]}/"><span class="num">{n:02d}</span>'
                     f'<span class="t">{esc(q["title"])}</span>{mark}</a></li>')
    if SERIES[key].get('more_coming'):
        items.append(f'<li class="upcoming">{esc(SERIES[key]["more_coming"])}</li>')
    return '<ol class="series-list">' + ''.join(items) + '</ol>'


PAGES_ICON = ('<svg class="pages-icon" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" '
              'stroke-width="1.5" stroke-linejoin="round" aria-hidden="true"><rect x="6.5" y="1.5" width="12" height="13" rx="1.2"/>'
              '<path d="M4 4.5v12.2c0 .5.3.8.8.8h10.7M1.5 7.5v10"/></svg>')


def _pitch_svg():
    """Flat top-down cricket pitch laid horizontally on a full-width band of striped grass: a rectangular strip
    with white popping creases near each end and return creases along its edges."""
    W, H = 300, 108
    bands = ''.join(
        f'<rect x="{x}" width="30.5" height="{H}" fill="{"#8dbb55" if (x // 30) % 2 == 0 else "#6fa043"}"/>'
        for x in range(0, W, 30)
    )
    return (
        f'<svg class="pitch-sketch" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
        '<defs><linearGradient id="pitch-sand" x1="0" x2="1"><stop offset="0" stop-color="#f3e0a0"/><stop offset="1" stop-color="#ecd48f"/></linearGradient></defs>'
        + bands +
        '<rect x="34" y="18" width="254" height="72" fill="url(#pitch-sand)"/>'
        '<g stroke="#fffbea" stroke-linecap="butt" fill="none">'
        '<path d="M74 6 L74 102" stroke-width="3.4"/><path d="M248 6 L248 102" stroke-width="3.4"/>'
        '<path d="M34 27 L74 27" stroke-width="2.8"/><path d="M34 81 L74 81" stroke-width="2.8"/>'
        '<path d="M248 27 L288 27" stroke-width="2.8"/><path d="M248 81 L288 81" stroke-width="2.8"/>'
        '</g></svg>'
    )


PITCH_SVG = _pitch_svg()


def series_block(key, v, sp):
    n = len(sp)
    unit = v.get('unit', ('story', 'stories'))[0 if n == 1 else 1]
    cover = v.get('cover') or next((q['cover'] for q in sp if q['cover']), None)
    img = f'<img src="{esc(local(cover, ""))}" alt="" loading="lazy" decoding="async">' if cover else ''
    if v.get('style') == 'pitch':
        return f'''<a class="book book-pitch book-score" href="#series-{key}" aria-label="{esc(v['title'])}, series, {n} {unit} so far">
  <span class="book-cover">
    {img}
    <span class="pitch-plate">{PITCH_SVG}<span class="pitch-text"><span class="book-kicker">Series · {n} {unit}</span><span class="book-title">{esc(v['title'])}</span></span></span>
    <span class="score-spiral" aria-hidden="true"></span>
  </span>
</a>'''
    if v.get('style') == 'snapshot':
        cap = f'<span class="snap-cap">{esc(v["caption"])}</span>' if v.get('caption') else ''
        return f'''<a class="book book-snap" href="#series-{key}" style="--spine:{v.get('spine', '#7A5A1E')}" aria-label="{esc(v['title'])}, series, {n} {unit} so far">
  <span class="book-cover leather">
    <span class="snap"><span class="snap-photo">{img}</span>{cap}</span>
    <span class="tape" aria-hidden="true"></span>
    <span class="book-spine" aria-hidden="true"></span>
    <span class="book-ribbon" aria-hidden="true"></span>
    <span class="snap-title"><span class="snap-kicker">Series · {n} {unit}</span><span class="snap-name">{esc(v['title'])}</span></span>
  </span>
</a>'''
    return f'''<a class="book" href="#series-{key}" style="--spine:{v.get('spine', '#2E4372')}" aria-label="{esc(v['title'])}, series, {n} {unit} so far">
  <span class="book-cover">
    {img}
    <span class="book-spine" aria-hidden="true"></span>
    <span class="book-ribbon" aria-hidden="true"></span>
    <span class="book-label">
      <span class="book-kicker">{PAGES_ICON}Series · {n} {unit}</span>
      <span class="book-title">{esc(v['title'])}</span>
    </span>
  </span>
</a>'''


STAR_ICON = ('<svg class="mark-star-svg" viewBox="0 0 16 16" width="15" height="15" fill="currentColor" aria-hidden="true">'
             '<path d="M8 1.2l2 4.3 4.7.6-3.4 3.2.9 4.7L8 11.7 3.8 14l.9-4.7L1.3 6.1 6 5.5z"/></svg>')

# tiny versions of the series covers, used as markers in the list
PAD_MINI = ('<svg class="mini-icon" viewBox="0 0 20 28" width="20" height="28" aria-hidden="true">'
            '<rect x="2" y="2" width="16" height="24" rx="1.4" fill="#8fb8dc"/><rect x="2" y="12" width="16" height="14" fill="#c4ad74"/>'
            '<rect x="2" y="17" width="16" height="6.4" fill="#7fae52"/><rect x="6" y="18.5" width="11" height="3.4" fill="#e6d395"/>'
            '<rect x="2" y="2" width="4.2" height="24" rx="1.4" fill="#7e1c26"/>'
            '<path d="M3.2 3.4v21.2M5 3.4v21.2" stroke="#f1d9db" stroke-width=".45" stroke-dasharray="1 1" fill="none"/></svg>')
BOOK_MINI = ('<svg class="mini-icon" viewBox="0 0 20 28" width="20" height="28" aria-hidden="true">'
             '<rect x="2" y="2" width="16" height="24" rx="1.6" fill="#7a5a1e"/><rect x="2" y="2" width="3.6" height="24" rx="1.4" fill="#58401a"/>'
             '<g transform="rotate(-7 12 10)"><rect x="7.6" y="5" width="8.6" height="8.6" fill="#fbf9f2"/><rect x="8.6" y="6" width="6.6" height="5.2" fill="#9db9a2"/></g>'
             '<rect x="7.4" y="18.6" width="9" height="1.5" rx=".75" fill="#ead9ab"/><path d="M13.6 2h2.4v6.4l-1.2-1.1-1.2 1.1z" fill="#c7a04a"/></svg>')
SERIES_MINI = {'pitch': PAD_MINI, 'snapshot': BOOK_MINI}


def uniq_ids(html_, suffix):
    """Keep SVG gradient ids unique when the same block appears twice on a page."""
    for i in ('pitch-sand',):
        html_ = html_.replace(f'id="{i}"', f'id="{i}{suffix}"').replace(f'url(#{i})', f'url(#{i}{suffix})')
    return html_


def build_index(posts):
    """One page, fixed order, nothing swaps: Pinned cards, Series, then the complete list (filters apply to the list only)."""
    rel = ''
    feat = sorted([p for p in posts if p['featured']], key=lambda p: p['featured'])[:4]
    pinned_slugs = {p['slug'] for p in feat}
    live_series = [(k, v, series_posts(posts, k)) for k, v in SERIES.items() if series_posts(posts, k)]

    # filters for the list: All | topics | series
    def chip(key, label, n, cls=''):
        return f'<button class="chip{cls}" data-key="{key}" aria-pressed="{"true" if key == "all" else "false"}">{label}<span class="n">{n}</span></button>'
    chips = [chip('all', 'All', len(posts))]
    for k, (_, plural) in FORMATS.items():
        n = sum(p['format'] == k for p in posts)
        if n and k not in NO_FORMAT_CHIP:
            chips.append(chip(k, plural, n))
    if live_series:
        chips.append('<span class="chip-sep" aria-hidden="true"></span>')
        chips += [chip(f'series-{k}', esc(v['title']), len(sp), ' chip-series') for k, v, sp in live_series]
    chips.append('<span class="chip-sep" aria-hidden="true"></span>')
    for t in TOPICS:
        n = sum(t in p['topics'] for p in posts)
        if n:
            chips.append(chip(slugify(t), esc(t), n))
    series_notes = ''
    for k, v, sp in live_series:
        n = len(sp)
        unit = v.get('unit', ('story', 'stories'))[0 if n == 1 else 1]
        more = f'<p class="series-hero-more">{esc(v["more_coming"])}</p>' if v.get('more_coming') else ''
        series_notes += f'''<div class="series-hero" data-key="series-{k}" hidden>
  {uniq_ids(series_block(k, v, sp), '-h')}
  <div class="series-hero-text">
    <p class="series-hero-eyebrow">Series · {n} {unit} so far</p>
    <h3>{esc(v['title'])}</h3>
    <p class="series-hero-blurb">{esc(v['blurb'])}</p>
    {more}
    <button class="note-clear" type="button">Show all writing ×</button>
  </div>
</div>'''

    pinned_items = [card(p, rel) for p in feat] + [series_block(k, v, sp) for k, v, sp in live_series[:3]]
    pinned_html = ''
    if pinned_items:
        pinned_html = (f'<section class="block pinned" aria-labelledby="pinned-h">\n  <h2 class="eyebrow" id="pinned-h">Recommended</h2>\n'
                       f'  <div class="feat-grid pinned-grid">{"".join(pinned_items)}</div>\n</section>')
    series_html = ''

    years = {}
    for p in posts:
        years.setdefault(p['date'].year, []).append(p)
    year_html = ''
    for y in sorted(years, reverse=True):
        rows = ''
        for p in years[y]:
            tags = ' '.join([p['format']] + [slugify(t) for t in p['topics']] + ([f'series-{p["series"]}'] if p['series'] else []))
            sr = SERIES.get(p['series']) if p['series'] else None
            if sr and sr.get('style') == 'snapshot':
                first, series_bit = f'<span class="fmt fmt-{p["format"]}">Diary Page</span>', ''
            else:
                first = fmt_badge(p)
                series_bit = ''
                if sr:
                    part = series_posts(posts, p['series']).index(p) + 1
                    series_bit = f'<span class="series-tag">{esc(sr["title"])} · {part:02d}</span>'
            bits = [first] + ([series_bit] if series_bit else []) + [f'<span>{esc(t)}</span>' for t in p['topics']] + [f'<span>{p["minutes"]} min</span>']
            marks_html = ''
            row_hook = (inline_md(p['excerpt']) + ' <span class="read-more">Read more...</span>') if p['excerpt'] else esc(p['hook'])
            thumb = thumb_for(p, '')
            thumb_html = f'\n  <span class="row-thumb"><img src="{esc(thumb)}" alt="" loading="lazy" decoding="async"></span>' if thumb else ''
            rows += f'''<li class="row{'' if thumb else ' no-thumb'}" data-tags="{tags}"><a href="{p['slug']}/">
  <span class="row-date">{p['date'].strftime('%b')}</span>
  <span class="row-main">{marks_html}
    <span class="row-title">{esc(p['title'])}</span>
    <span class="row-hook">{row_hook}</span>
    <span class="row-meta">{''.join(bits)}</span>
  </span>{thumb_html}</a></li>'''
        year_html += f'<div class="year"><h3 class="year-label">{y}</h3><ul class="rows">{rows}</ul></div>'

    works = ''
    if BLOG['in_the_works']:
        boxes = ''.join(f'<div class="soon-box"><div class="soon-art" aria-hidden="true"></div><p class="soon-title">{esc(w)}</p></div>' for w in BLOG['in_the_works'])
        works = f'<section class="block" aria-labelledby="soon-h">\n  <h2 class="eyebrow" id="soon-h">Coming soon</h2>\n  <div class="soon-grid">{boxes}</div>\n</section>'

    sub = BLOG.get('subtitle')
    head, _, last = BLOG['title'].rpartition(' ')
    h1_text = f'{esc(head)} <span class="nowrap">{esc(last)}<span class="dots">…</span></span>' if head else esc(BLOG['title'])
    h1_html = f'<h1 class="has-sub">{h1_text}</h1>\n  <p class="subtitle">{esc(sub)}</p>' if sub else f'<h1>{h1_text}</h1>'
    body = f'''<main id="content" class="wrap">
<section class="intro">
  <p class="eyebrow">Writing</p>
  {h1_html}
  <p class="lede">{esc(BLOG['intro'])}</p>
  <p class="meta-links">Read something? I’d love to hear what you think, <a href="{BLOG['feedback']}" target="_blank" rel="noopener">anonymously</a>.</p>
</section>
{pinned_html}
{series_html}
<section class="block archive" aria-labelledby="all-h">
  <div class="archive-head"><h2 class="eyebrow read-all" id="all-h">Browse all <span aria-hidden="true">›</span></h2><span class="archive-count" aria-live="polite">{len(posts)} pieces</span></div>
  <div class="filters" role="group" aria-label="Filter writing">{''.join(chips)}</div>
  {series_notes}
  {year_html}
  <p class="empty" hidden>Nothing here yet.</p>
</section>
{works}
</main>'''
    return page(rel=rel, title=f'{BLOG["title"]} · Writing by Aditya Mate', desc=BLOG['intro'],
                url='/blog/', image=feat[0]['cover'] if feat else None, body=body, og_type='website')


def build_post(p, posts):
    rel = '../'
    series_box = pill = ''
    if p['series']:
        sp = series_posts(posts, p['series'])
        part = sp.index(p) + 1
        s = SERIES[p['series']]
        pill = f'<a class="series-pill" href="../#series-{p["series"]}">{esc(s["title"])} · Part {part}</a>'
        series_box = f'''<aside class="series-box" aria-labelledby="sb-h">
  <p class="eyebrow">Part of a series</p>
  <h2 id="sb-h">{esc(s['title'])}</h2>
  {series_list(posts, p['series'], rel, current=p)}
</aside>'''
    # keep reading: the next older and next newer pieces outside this series
    others = [q for q in posts if q is not p and (not p['series'] or q['series'] != p['series'])]
    older = [q for q in others if q['date'] < p['date']]
    newer = [q for q in others if q['date'] >= p['date']][::-1]
    picks = (newer[:1] + older[:1]) or others[:2]
    if len(picks) < 2:
        picks += [q for q in others if q not in picks][:2 - len(picks)]
    keep = ''
    if picks:
        keep = f'''<section class="keep" aria-labelledby="keep-h">
  <h2 class="eyebrow" id="keep-h">Keep reading</h2>
  <div class="keep-grid">{''.join(card(q, rel, 'small') for q in picks)}</div>
</section>'''
    body = f'''<main id="content" class="post">
<a class="back" href="../">← All writing</a>
<header class="post-head">
  <p class="kicker">{fmt_badge(p)}<span>{esc(p['date_label'])}</span><span>{p['minutes']} min read</span></p>
  <h1>{esc(p['title'])}</h1>
  {f'<p class="dek">{esc(p["hook"])}</p>' if p['hook'] else ''}
  {pill}
</header>
<article class="prose {p['format']}">
{render_body(p, rel)}
</article>
{series_box}
<p class="post-feedback">Enjoyed this, or didn’t? <a href="{BLOG['feedback']}" target="_blank" rel="noopener">Tell me anonymously</a>.</p>
{keep}
</main>'''
    return page(rel=rel, title=f'{p["title"]} · Aditya Mate', desc=p['hook'] or BLOG['intro'],
                url=f'/blog/{p["slug"]}/', image=p['cover'], body=body)


def build_feed(posts):
    items = ''.join(f'''
  <item>
    <title>{esc(p['title'])}</title>
    <link>{SITE}/blog/{p['slug']}/</link>
    <guid>{SITE}/blog/{p['slug']}/</guid>
    <pubDate>{datetime.datetime.combine(p['date'], datetime.time(12)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
    <description>{esc(p['hook'])}</description>
  </item>''' for p in posts)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{esc(BLOG['title'])} · Aditya Mate</title>
  <link>{SITE}/blog/</link>
  <description>{esc(BLOG['intro'])}</description>{items}
</channel>
</rss>
'''


def build_sitemap(posts):
    urls = [('/', '1.0'), ('/publications.html', '0.8')]
    if not UNLISTED:
        urls += [('/blog/', '0.8')] + [(f'/blog/{p["slug"]}/', '0.6') for p in posts]
    body = ''.join(f'\n  <url>\n    <loc>{SITE}{u}</loc>\n    <priority>{pr}</priority>\n  </url>' for u, pr in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}\n</urlset>\n'


def main():
    posts = [parse_post(f) for f in sorted((SRC / 'posts').glob('*.md'))]
    posts = sorted([p for p in posts if not p['draft']], key=lambda p: p['date'], reverse=True)
    slugs = [p['slug'] for p in posts]
    dup = {s for s in slugs if slugs.count(s) > 1}
    if dup:
        sys.exit(f'Duplicate slugs: {dup}')
    OUT.mkdir(exist_ok=True)
    # remove pages for posts that no longer exist
    for d in OUT.iterdir():
        if d.is_dir() and (d / 'index.html').exists() and d.name not in slugs and d.name != 'img':
            shutil.rmtree(d)
    for asset in ('blog.css', 'blog.js', 'bridge.jpg'):
        shutil.copyfile(SRC / asset, OUT / asset)
    (OUT / 'index.html').write_text(build_index(posts), encoding='utf-8')
    for p in posts:
        (OUT / p['slug']).mkdir(exist_ok=True)
        (OUT / p['slug'] / 'index.html').write_text(build_post(p, posts), encoding='utf-8')
    (OUT / 'feed.xml').write_text(build_feed(posts), encoding='utf-8')
    (ROOT / 'sitemap.xml').write_text(build_sitemap(posts), encoding='utf-8')
    thumbs = OUT / 'img' / 'thumbs'
    if thumbs.exists():
        for f in thumbs.iterdir():
            if f.name not in USED_THUMBS:
                f.unlink()
    print(f'Built {len(posts)} posts into blog/')
    if '--serve' in sys.argv:
        import functools, http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        print('Preview: http://localhost:8000/blog/   (Ctrl+C to stop)')
        http.server.ThreadingHTTPServer(('localhost', 8000), handler).serve_forever()


if __name__ == '__main__':
    main()
