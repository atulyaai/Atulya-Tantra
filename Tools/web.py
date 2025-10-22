import requests


def web_search(query: str, limit: int = 3) -> str:
    try:
        r = requests.get('https://api.duckduckgo.com/', params={'q': query, 'format': 'json', 'no_html': 1, 'no_redirect': 1}, timeout=5)
        if r.status_code != 200:
            return "Couldn't reach search service."
        data = r.json()
        out = []
        if data.get('AbstractText'):
            out.append(data['AbstractText'])
        for topic in data.get('RelatedTopics', [])[:limit]:
            if isinstance(topic, dict) and topic.get('Text'):
                out.append(topic['Text'])
        return '\n'.join(out[:limit]) or 'No results.'
    except Exception:
        return 'Search error.'


def wiki_summary(topic: str) -> str:
    try:
        r = requests.get(f'https://en.wikipedia.org/api/rest_v1/page/summary/{topic}', timeout=5)
        if r.status_code != 200:
            return 'No summary found.'
        data = r.json()
        return data.get('extract', 'No summary found.')
    except Exception:
        return 'Summary error.'


