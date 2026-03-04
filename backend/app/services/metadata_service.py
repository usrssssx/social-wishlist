from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

PRICE_META_KEYS = [
    ('property', 'product:price:amount'),
    ('property', 'og:price:amount'),
    ('name', 'price'),
    ('itemprop', 'price'),
]


def _safe_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = re.sub(r'[^\d.,]', '', value).replace(',', '.')
    if cleaned.count('.') > 1:
        cleaned = cleaned.replace('.', '', cleaned.count('.') - 1)
    try:
        return Decimal(cleaned).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return None


def _absolute_url(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    parsed = urlparse(maybe_relative)
    if parsed.scheme and parsed.netloc:
        return maybe_relative
    base = urlparse(base_url)
    if maybe_relative.startswith('//'):
        return f'{base.scheme}:{maybe_relative}'
    if maybe_relative.startswith('/'):
        return f'{base.scheme}://{base.netloc}{maybe_relative}'
    return f'{base.scheme}://{base.netloc}/{maybe_relative}'


async def scrape_product_metadata(url: str) -> dict[str, str | Decimal | None]:
    timeout = httpx.Timeout(8.0, connect=5.0)
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/126.0.0.0 Safari/537.36'
        )
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    title = None
    image_url = None
    price = None

    title_tag = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'twitter:title'})
    if title_tag and title_tag.get('content'):
        title = title_tag['content'].strip()
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    image_tag = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
    if image_tag and image_tag.get('content'):
        image_url = _absolute_url(str(response.url), image_tag['content'].strip())

    for key, value in PRICE_META_KEYS:
        price_tag = soup.find('meta', attrs={key: value})
        if price_tag and price_tag.get('content'):
            price = _safe_decimal(price_tag['content'])
            if price is not None:
                break

    if price is None:
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                raw = script.string or ''
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            blocks = data if isinstance(data, list) else [data]
            for block in blocks:
                offers = block.get('offers') if isinstance(block, dict) else None
                if isinstance(offers, dict):
                    price = _safe_decimal(str(offers.get('price')))
                    if price is not None:
                        break
            if price is not None:
                break

    return {
        'title': title,
        'image_url': image_url,
        'price': price,
        'url': str(response.url),
    }
