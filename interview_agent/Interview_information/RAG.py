import re, requests, httpx
import asyncio
import os
from vectorCollection import create_collection, store
from readability import Document
from lxml import etree

create_collection()

response = requests.get("https://raw.githubusercontent.com/DopplerHQ/awesome-interview-questions/master/README.md")

readme = response.text
content = readme.split("## Programming Languages/Frameworks/Platforms")[1]

scrapeRequests = []
documents = []

async def scrapeUrl(url: str, text: str) -> None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                follow_redirects=True
            )
            if response.status_code == 200:
                doc = Document(response.text)
                root = etree.fromstring(doc.summary(), etree.HTMLParser())
                
                # Remove noisy tags
                for tag in root.xpath('//code|//pre|//table|//figure|//img|//script|//style'):
                    tag.getparent().remove(tag)
                
                plain_text = ' '.join(root.itertext())
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                
                document = {'title': text, 'url': url, 'content': plain_text}
                documents.append(document)
    except Exception:
        return None

async def addToVectorDatabase(documents: list[dict]):
    store(documents)

def findLinks():
    for match in re.finditer(r'\[(.+?)\]\((https?://[^\)]+)\)', content):
        scrapeRequests.append((match.group(1), match.group(2)))

findLinks()

async def scrapeData():
    results = await asyncio.gather(*[scrapeUrl(url, text) for text, url in scrapeRequests])
    await addToVectorDatabase(documents)
    return results

asyncio.run(scrapeData())

