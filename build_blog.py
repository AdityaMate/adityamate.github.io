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
    featured: 1              # optional, 1-3 = position in "Start here"
    cover: /blog/img/my-photo.jpg   # optional card image
    hook: One or two sentences that make people want to click.
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
    'title': 'Off the Clock',
    'intro': ('My non-technical, non-serious corner of the internet: curious stories, '
              'armchair thoughts, travel accounts, and the odd page from my diary.'),
    'feedback': 'https://docs.google.com/forms/d/e/1FAIpQLSeq8BZfUlsnZ-JsNJCu9C_hOrYUOk3JcfokS55Jc4S9epCujA/viewform?usp=sf_link',
    'in_the_works': [],   # e.g. ['First impressions of the City of Angels']
}
SERIES = {
    'crease': {
        'title': 'Tales from the Crease',
        'blurb': ('Stories from matches I’ve played: the collapses, the comebacks, '
                  'and the baseball player who out-batted all of us.'),
        'more_coming': 'More match stories on the way',
    },
    'diary': {
        'title': 'Pages from My Diary',
        'blurb': ('Unpolished pages from my diary: the trips, reunions and ordinary days '
                  'I would happily freeze in time.'),
        'more_coming': 'More pages on the way',
        'unit': ('page', 'pages'),
    },
}
# formats whose filter chip is left out because a series already covers them
NO_FORMAT_CHIP = {'diary'}
# keys are what you write in front matter (format: essay); the labels are what readers see
FORMATS = {'essay': ('Story', 'Stories'), 'note': ('Note', 'Notes'), 'diary': ('Diary', 'Diary')}
TOPICS = ['Cricket', 'Travel', 'Work & Study', 'Life']
# -------------------------------------------------------------------------

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
<link rel="stylesheet" href="{rel}blog.css">
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
<script src="{rel}blog.js" defer></script>
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


def build_index(posts):
    rel = ''
    feat = sorted([p for p in posts if p['featured']], key=lambda p: p['featured'])[:3]
    feat_html = ''
    if feat:
        cards = [card(feat[0], rel, 'lead')] + [card(p, rel) for p in feat[1:]]
        feat_html = f'''<section class="block" aria-labelledby="start-h">
  <h2 class="eyebrow" id="start-h">Start here</h2>
  <div class="feat-grid">{''.join(cards)}</div>
</section>'''

    series_html = ''
    for key, s in SERIES.items():
        sp = series_posts(posts, key)
        if not sp:
            continue
        n = len(sp)
        series_html += f'''<section class="block" id="series-{key}" aria-labelledby="s-{key}">
  <div class="series-card">
    <div>
      <p class="eyebrow">Series · {n} {s.get('unit', ('story', 'stories'))[0 if n == 1 else 1]} so far</p>
      <h2 class="series-title" id="s-{key}">{esc(s['title'])}</h2>
      <p class="blurb">{esc(s['blurb'])}</p>
    </div>
    {series_list(posts, key, rel)}
  </div>
</section>'''

    # filter chips: only show ones that have posts
    chips = [f'<button class="chip" data-key="all" aria-pressed="true">All<span class="n">{len(posts)}</span></button>']
    for k, (_, plural) in FORMATS.items():
        n = sum(p['format'] == k for p in posts)
        if n and k not in NO_FORMAT_CHIP:
            chips.append(f'<button class="chip" data-key="{k}" aria-pressed="false">{plural}<span class="n">{n}</span></button>')
    chips.append('<span class="chip-sep" aria-hidden="true"></span>')
    for t in TOPICS:
        n = sum(t in p['topics'] for p in posts)
        if n:
            chips.append(f'<button class="chip" data-key="{slugify(t)}" aria-pressed="false">{esc(t)}<span class="n">{n}</span></button>')

    years = {}
    for p in posts:
        years.setdefault(p['date'].year, []).append(p)
    year_html = ''
    for y in sorted(years, reverse=True):
        rows = ''
        for p in years[y]:
            tags = ' '.join([p['format']] + [slugify(t) for t in p['topics']])
            bits = [fmt_badge(p)] + [f'<span>{esc(t)}</span>' for t in p['topics']] + [f'<span>{p["minutes"]} min</span>']
            if p['series']:
                part = series_posts(posts, p['series']).index(p) + 1
                bits.append(f'<span class="series-tag">{esc(SERIES[p["series"]]["title"])} · {part:02d}</span>')
            thumb = thumb_for(p, '')
            thumb_html = f'\n  <span class="row-thumb"><img src="{esc(thumb)}" alt="" loading="lazy" decoding="async"></span>' if thumb else ''
            rows += f'''<li class="row{'' if thumb else ' no-thumb'}" data-tags="{tags}"><a href="{p['slug']}/">
  <span class="row-date">{p['date'].strftime('%b')}</span>
  <span class="row-main">
    <span class="row-title">{esc(p['title'])}</span>
    <span class="row-hook">{esc(p['hook'])}</span>
    <span class="row-meta">{''.join(bits)}</span>
  </span>{thumb_html}</a></li>'''
        year_html += f'<div class="year"><h3 class="year-label">{y}</h3><ul class="rows">{rows}</ul></div>'

    works = ''
    if BLOG['in_the_works']:
        works = '<p class="in-works">In the works: ' + ' · '.join(esc(w) for w in BLOG['in_the_works']) + '</p>'

    body = f'''<main id="content" class="wrap">
<section class="intro">
  <p class="eyebrow">Writing</p>
  <h1>{esc(BLOG['title'])}</h1>
  <p class="lede">{esc(BLOG['intro'])}</p>
  <p class="meta-links">Read something? I’d love to hear what you think, <a href="{BLOG['feedback']}" target="_blank" rel="noopener">anonymously</a>.</p>
</section>
{feat_html}
{series_html}
<section class="block archive" aria-labelledby="all-h">
  <div class="archive-head"><h2 class="eyebrow" id="all-h">All writing</h2><span class="archive-count" aria-live="polite">{len(posts)} pieces</span></div>
  <div class="filters" role="group" aria-label="Filter writing">{''.join(chips)}</div>
  {year_html}
  <p class="empty" hidden>Nothing here yet.</p>
  {works}
</section>
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
    for asset in ('blog.css', 'blog.js'):
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
