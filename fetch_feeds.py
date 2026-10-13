"""Lists for thibaultschrepel.com, refreshed by GitHub Actions (.github/workflows/feeds.yml).

newsletter.json  the posts of The Competition System (Substack)
podcasts.json    the episodes of Scaling Theory and of Stanford Computational Antitrust
nlr.json         Thibault Schrepel's own articles in the Network Law Review (the journal also publishes other
                 authors: an article counts as his when its citation line names him), without the monthly
                 reading suggestions

Substack does not let a web page read its posts from another site, so this script copies them into
this repository, next to strava.json. The website reads both files from raw.githubusercontent.com.
Standard library only. A source that cannot be reached leaves its file as it was."""
import json
import re
import sys
from html import unescape
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBSTACK = 'https://thecompetitionsystem.substack.com'
SKIP = {'the-competition-system'}  # the welcome post
SHOWS = {
    'scaling': 'https://anchor.fm/s/f3a5f9e4/podcast/rss',
    'sca': 'https://anchor.fm/s/b99a0128/podcast/rss',
}
ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; thibaultschrepel.com feeds)', 'Accept': '*/*'}


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def text(node, tag):
    return (node.findtext(tag) or '').strip()


def slug(url):
    return url.split('?')[0].rstrip('/').split('/')[-1]


def posts_from_api():
    posts, offset = [], 0
    while True:
        batch = json.loads(get(f'{SUBSTACK}/api/v1/archive?sort=new&offset={offset}&limit=50'))
        if not batch:
            break
        for p in batch:
            if p.get('slug') in SKIP or p.get('type') not in ('newsletter', 'podcast'):
                continue
            posts.append({'title': (p.get('title') or '').strip(),
                          'url': p.get('canonical_url') or f"{SUBSTACK}/p/{p.get('slug')}",
                          'date': (p.get('post_date') or '')[:10]})
        offset += len(batch)
        if len(batch) < 50:
            break
    return posts


def posts_from_feed():
    root = ET.fromstring(get(f'{SUBSTACK}/feed'))
    posts = []
    for it in root.find('channel').findall('item'):
        url = text(it, 'link')
        if slug(url) in SKIP:
            continue
        posts.append({'title': text(it, 'title'), 'url': url,
                      'date': parsedate_to_datetime(text(it, 'pubDate')).strftime('%Y-%m-%d')})
    return posts


def newsletter(old):
    try:
        posts, complete = posts_from_api(), True
    except Exception as err:
        print('Substack archive not reachable, reading the feed:', err, file=sys.stderr)
        posts, complete = posts_from_feed(), False
    posts = [p for p in posts if p.get('title') and p.get('url') and p.get('date')]
    if not complete:
        # the feed only carries the latest posts: the older ones come from the last copy
        posts += [p for p in old.get('posts', []) if isinstance(p, dict) and p.get('title') and p.get('url') and p.get('date')]
    out, seen = [], set()
    for p in sorted(posts, key=lambda p: p['date'], reverse=True):
        if slug(p['url']) in seen:
            continue
        seen.add(slug(p['url']))
        out.append({'title': p['title'], 'url': p['url'], 'date': p['date']})
    if not out:
        raise RuntimeError('no post found')
    return {'title': 'The Competition System', 'url': SUBSTACK, 'posts': out}


def show(feed):
    ch = ET.fromstring(get(feed)).find('channel')
    eps = []
    for it in ch.findall('item'):
        eps.append({'title': text(it, 'title'), 'url': text(it, 'link'),
                    'date': parsedate_to_datetime(text(it, 'pubDate')).strftime('%Y-%m-%d'),
                    'duration': text(it, ITUNES + 'duration')})
    eps = [e for e in eps if e['title'] and e['url']]
    if not eps:
        raise RuntimeError('the feed lists no episode')
    eps.sort(key=lambda e: e['date'], reverse=True)
    return {'title': text(ch, 'title'), 'url': text(ch, 'link'), 'episodes': eps}


NLR_API = 'https://www.networklawreview.org/wp-json/wp/v2/posts'
NLR_SKIP = ('reading suggestions', 'links of', 'links -', 'liens ')


def plain(html_text):
    t = re.sub(r'<[^>]+>', ' ', html_text or '')
    return re.sub(r'\s+', ' ', unescape(t)).strip()


def nlr_page(page, per_page=100):
    url = f'{NLR_API}?per_page={per_page}&page={page}&_fields=id,date,link,title,content'
    return json.loads(get(url).decode('utf-8'))


def is_his(text):
    """The authors of the citation line, before the first comma, include him."""
    for m in re.finditer(r'Citation\s*:', text):
        if 'Schrepel' in text[m.end():m.end() + 160].split(',')[0]:
            return True
    return False


def nlr(old):
    """New posts are read from the latest page; the whole archive only when the file does not exist yet."""
    known = {a['id']: a for a in old.get('articles', [])}
    pages = range(1, 30) if not known else [1]
    for page in pages:
        batch = None
        for attempt in range(3):
            try:
                batch = nlr_page(page)
                break
            except Exception as err:
                last = err
        if batch is None:
            raise RuntimeError(f'page {page} could not be read: {last}')
        if not batch:
            break
        for p in batch:
            title = re.sub(r'^Thibault Schrepel\s*:\s*', '', plain(p['title']['rendered'])).strip()
            if title.startswith('\u201c') and title.endswith('\u201d'):
                title = title[1:-1]
            if title.lower().startswith(NLR_SKIP):
                continue
            body = plain(p['content']['rendered'])
            if not is_his(body):
                continue
            known[p['id']] = {'id': p['id'], 'title': title, 'url': p['link'], 'date': p['date'][:10],
                              'abstract': body[:600]}
    arts = sorted(known.values(), key=lambda a: a['date'], reverse=True)
    if not arts:
        raise RuntimeError('no article found')
    return {'title': 'Network Law Review', 'url': 'https://www.networklawreview.org/', 'articles': arts}


def load(name):
    path = HERE / name
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def main():
    try:
        news = newsletter(load('newsletter.json'))
        save('newsletter.json', news)
        print('newsletter:', len(news['posts']), 'posts')
    except Exception as err:
        print('newsletter left as it was:', err, file=sys.stderr)
    pods = load('podcasts.json')
    for key, feed in SHOWS.items():
        try:
            pods[key] = show(feed)
            print(key + ':', len(pods[key]['episodes']), 'episodes')
        except Exception as err:
            print(key, 'left as it was:', err, file=sys.stderr)
    if pods:
        save('podcasts.json', pods)
    try:
        arts = nlr(load('nlr.json'))
        save('nlr.json', arts)
        print('nlr:', len(arts['articles']), 'articles')
    except Exception as err:
        print('nlr left as it was:', err, file=sys.stderr)


if __name__ == '__main__':
    main()
