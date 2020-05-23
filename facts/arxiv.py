import logging
import typing
import re
import sys
import json
import requests
import feedparser
import click
import time
import urllib.parse
import glob
from datetime import datetime

from facts.core import workflow

logger = logging.getLogger()

PaperEntry = typing.NewType("PaperEntry", dict)

@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
def cli(debug):
    if debug:
        logger.setLevel(logging.DEBUG)


class BoringPaper(Exception):
    "boring"


@cli.command()
@click.option("-s", "--search-string")
@click.option("-c", "--category", default="astro-ph.*")
@click.option("-n", "--max-results", default=10)
def fetch(search_string, max_results, category):
    cats=[
            "astro-ph",
            "astro-ph.GA",
            "astro-ph.CO",
            "astro-ph.EP",
            "astro-ph.HE",
            "astro-ph.IM",
            "astro-ph.SR",
        ]

    for cat in cats:
        if not re.search(category, cat):
            continue

        logger.info(f"fetching category {cat} (matches {category})")

        s = f"cat:{cat}"
        if search_string != "":
            s = f"{s} AND {search_string}"

        def getBy(sortBy):
            params = dict(
                search_query=f'{s}',
                sortBy=sortBy,
                sortOrder='descending',
                max_results=max_results
            )

            r = requests.get('http://export.arxiv.org/api/query?'+ urllib.parse.urlencode(params, doseq=True))

            feed = feedparser.parse(r.text)
            json.dump(feed, open(f"papers-recent-{cat}-{sortBy}.json", "w"))

            for entry in feed['entries']:
                logger.debug(f'fetched {entry["id"].split("/")[-1]} ({entry["updated"]}): {entry["title"]}')

        getBy("lastUpdatedDate")
        getBy("submittedDate")

@cli.command()
def fetch_recent():
    r = requests.get('http://arxiv.org/rss/astro-ph')
    json.dump(feedparser.parse(r.text), open("papers-recent.json", "w"))

@workflow
def basic_meta(entry: PaperEntry):  # ->
    return dict(
                location=entry['id'], 
                title=re.sub(r"[\n\r]", " ", entry['title']),
            )

@workflow
def basic_time_meta(entry: PaperEntry):  # ->
    updated_ts = datetime.fromisoformat(entry['updated'].replace('Z',"")).timestamp()
    return dict(
                updated_isot=entry['updated'],
                updated_ts=updated_ts,
            )


@workflow
def mentions_keyword(entry: PaperEntry):  # ->
    d = {}

    for keyword in "INTEGRAL", "FRB", "GRB", "GW170817", "GW190425", "magnetar", "SGR":
        k = keyword.lower()

        for field in 'title', 'summary':
            n = len(re.findall(keyword, entry[field]))
            if n>0:
                d['mentions_'+k] = field
            if n>1:
                d['mentions_'+k+'_times'] = n
        

    return d

@workflow
def list_entries() -> typing.List[PaperEntry]:
    es = []
    for fn in glob.glob("papers-*json"):
        es += json.load(open(fn))['entries']

    return es

@workflow
def identity(entry: PaperEntry) -> str:
    return 'http://odahub.io/ontology/paper#arXiv'+entry['id'].split("/")[-1]

if __name__ == "__main__":
    cli()