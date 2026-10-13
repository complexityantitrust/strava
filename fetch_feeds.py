"""Lists for thibaultschrepel.com, refreshed by GitHub Actions (.github/workflows/feeds.yml).

newsletter.json  the posts of The Competition System (Substack)
podcasts.json    the episodes of Scaling Theory and of Stanford Computational Antitrust

Substack does not let a web page read its posts from another site, so this script copies them into
this repository, next to strava.json. The website reads both files from raw.githubusercontent.com.
Standard library only. A source that cannot be reached leaves its file as it was."""
import json
import sys
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


if __name__ == '__main__':
    main()
