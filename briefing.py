"""Tägliches Politik-Briefing Region Basel.

Holt Medien-Schlagzeilen (Google News RSS, optionale Direkt-Feeds) und neue
Geschäfte des Grossen Rats BS (data.bs.ch), entfernt Duplikate, gruppiert nach
Themen und schreibt eine HTML-Seite nach docs/. Ist ANTHROPIC_API_KEY gesetzt,
schreibt Claude oben eine Kurz-Zusammenfassung.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config

TZ = ZoneInfo("Europe/Zurich")
ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
UA = {"User-Agent": "Mozilla/5.0 (compatible; news-briefing/1.0)"}


@dataclass
class Item:
    title: str
    link: str
    source: str
    published: datetime | None
    teaser: str = ""
    kind: str = "medien"  # medien | parlament


@dataclass
class Story:
    items: list[Item]
    topic: str = "Weitere Themen"

    @property
    def lead(self) -> Item:
        return max(self.items, key=lambda i: len(i.teaser))

    @property
    def sources(self) -> list[str]:
        return sorted({i.source for i in self.items})

    @property
    def latest(self) -> datetime | None:
        ds = [i.published for i in self.items if i.published]
        return max(ds) if ds else None


@dataclass
class Report:
    date: str
    stories: list[Story] = field(default_factory=list)
    parlament: list[Item] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- Abrufen

def clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_feed(content: bytes, default_source: str) -> list[Item]:
    import feedparser

    feed = feedparser.parse(content)
    items = []
    for e in feed.entries:
        title = clean_text(e.get("title", ""))
        source = default_source
        src = e.get("source")
        if src and src.get("title"):
            source = src["title"]
            # Google News hängt " - Quelle" an den Titel
            suffix = f" - {source}"
            if title.endswith(suffix):
                title = title[: -len(suffix)]
        published = None
        if e.get("published_parsed"):
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        teaser = clean_text(e.get("summary", ""))
        # Google-News-Teaser wiederholen meist nur den Titel
        if teaser.startswith(title[:40]):
            teaser = ""
        if title:
            items.append(Item(title, e.get("link", ""), source, published, teaser[:400]))
    return items


def fetch_media(errors: list[str]) -> list[Item]:
    import requests

    urls = [
        ("Google News",
         "https://news.google.com/rss/search?" + urllib.parse.urlencode(
             {"q": q, "hl": "de-CH", "gl": "CH", "ceid": "CH:de"}))
        for q in config.GOOGLE_NEWS_QUERIES
    ] + list(config.DIRECT_FEEDS)
    items: list[Item] = []
    for name, url in urls:
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            items += parse_feed(r.content, name)
        except Exception as exc:  # eine kaputte Quelle darf nicht alles stoppen
            errors.append(f"{name}: {type(exc).__name__} ({url[:80]})")
    return items


def _pick(fields: list[dict], *needles: str, types: tuple[str, ...] = ()) -> str | None:
    for needle in needles:
        for f in fields:
            if needle in f["name"].lower() and (not types or f.get("type") in types):
                return f["name"]
    return None


def fetch_grosser_rat(errors: list[str]) -> list[Item]:
    """Neue Geschäfte Grosser Rat BS. Feldnamen werden aus den Metadaten gelesen,
    damit eine Schema-Änderung nicht sofort alles bricht."""
    import requests

    base = f"https://data.bs.ch/api/explore/v2.1/catalog/datasets/{config.GROSSER_RAT_DATASET}"
    try:
        meta = requests.get(base, headers=UA, timeout=20).json()
        fields = meta.get("fields", [])
        date_f = _pick(fields, "beginn", "datum", "date", types=("date", "datetime"))
        title_f = _pick(fields, "titel", "title", "bezeichnung")
        link_f = _pick(fields, "url", "link")
        type_f = _pick(fields, "geschaftstyp", "geschäftstyp", "typ", "art")
        sig_f = _pick(fields, "signatur", "nummer")
        if not (date_f and title_f):
            raise ValueError(f"Felder nicht erkannt: {[f['name'] for f in fields]}")
        since = (datetime.now(TZ) - timedelta(days=config.GROSSER_RAT_DAYS)).date().isoformat()
        r = requests.get(f"{base}/records", headers=UA, timeout=20, params={
            "where": f"{date_f} >= date'{since}'",
            "order_by": f"{date_f} desc",
            "limit": 50,
        })
        r.raise_for_status()
        out = []
        for rec in r.json().get("results", []):
            d = rec.get(date_f)
            published = datetime.fromisoformat(d[:10]).replace(tzinfo=TZ) if d else None
            label = " · ".join(str(rec[f]) for f in (sig_f, type_f) if f and rec.get(f))
            out.append(Item(
                title=str(rec.get(title_f, "")).strip(),
                link=str(rec.get(link_f) or "https://grosserrat.bs.ch/"),
                source="Grosser Rat BS",
                published=published,
                teaser=label,
                kind="parlament",
            ))
        return out
    except Exception as exc:
        errors.append(f"Grosser Rat BS (data.bs.ch): {type(exc).__name__}: {exc}"[:200])
        return []


# ---------------------------------------------------------------- Verarbeiten

STOP = set("""der die das und oder in im am an auf für von mit zu zum zur ist sind ein eine einen
           des dem den nach bei aus wie was wer will soll sich nicht auch es er sie wir basel
           basler baselland baselbieter kanton stadt neue neuer neues über vor gegen""".split())


def tokens(title: str) -> set[str]:
    words = re.findall(r"[a-zäöüéèà0-9]+", title.lower())
    return {w for w in words if w not in STOP and len(w) > 2}


def cluster(items: list[Item], threshold: float = 0.45) -> list[Story]:
    stories: list[tuple[set[str], Story]] = []
    seen_links = set()
    for it in sorted(items, key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        if it.link in seen_links:
            continue
        seen_links.add(it.link)
        tk = tokens(it.title)
        for stk, story in stories:
            if tk and stk and len(tk & stk) / min(len(tk), len(stk)) >= threshold:
                story.items.append(it)
                stk |= tk
                break
        else:
            stories.append((set(tk), Story([it])))
    return [s for _, s in stories]


def classify(story: Story) -> str:
    text = " " + " ".join(f"{i.title} {i.teaser}" for i in story.items).lower() + " "
    best, score = "Weitere Themen", 0
    for topic, words in config.TOPICS.items():
        n = sum(text.count(w) for w in words)
        if n > score:
            best, score = topic, n
    return best


def within_window(items: list[Item], hours: int) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [i for i in items if i.published is None or i.published >= cutoff]


# ---------------------------------------------------------------- Claude

SYSTEM_PROMPT = """Du bist Assistenz einer Kommunikationsfachperson in Basel. Du erhältst die \
Schlagzeilen (und, wo vorhanden, Teaser) der letzten 24 Stunden zur Politik in Basel-Stadt und \
Basel-Landschaft sowie neue Geschäfte des Grossen Rats.

Schreibe ein Morgen-Briefing auf Schweizer Hochdeutsch (ss statt ß):
- 4 bis 6 Punkte, jeder 1–2 Sätze, das Wichtigste zuerst.
- Gewichte nach politischer Tragweite und danach, wie viele Medien berichten.
- Stütze dich ausschliesslich auf die gelieferten Angaben. Erfinde keine Details, Zahlen oder \
Zitate. Wo nur eine Schlagzeile vorliegt, formuliere entsprechend vorsichtig.
- Nenne am Ende jedes Punkts in Klammern die Nummer(n) der Quelle(n), z. B. [3, 7].

Gib nur die Punkte aus, jede Zeile beginnend mit "- ", ohne Einleitung oder Schluss."""


def summarize(stories: list[Story], parlament: list[Item], errors: list[str]) -> list[str]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return []
    import anthropic

    lines = []
    for n, s in enumerate(stories[: config.MAX_ITEMS_FOR_SUMMARY], 1):
        lead = s.lead
        lines.append(f"[{n}] {lead.title} — Quellen: {', '.join(s.sources)}"
                     + (f"\n    {lead.teaser}" if lead.teaser else ""))
    if parlament:
        lines.append("\nNeue Geschäfte Grosser Rat BS:")
        lines += [f"- {p.title} ({p.teaser})" for p in parlament[:20]]

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=4000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(lines)}],
        )
    except anthropic.APIStatusError as exc:
        errors.append(f"Claude: HTTP {exc.status_code} – {exc.message}"[:200])
        return []
    except anthropic.APIConnectionError:
        errors.append("Claude: keine Verbindung")
        return []
    if response.stop_reason == "refusal":
        errors.append("Claude: Zusammenfassung abgelehnt")
        return []
    text = "".join(b.text for b in response.content if b.type == "text")
    return [l[2:].strip() for l in text.splitlines() if l.startswith("- ")]


# ---------------------------------------------------------------- HTML

def fmt_time(d: datetime | None) -> str:
    return d.astimezone(TZ).strftime("%d.%m. %H:%M") if d else ""


def render(report: Report, archive: list[str]) -> str:
    e = html.escape
    numbered = {n: s for n, s in enumerate(report.stories, 1)}

    def cite(line: str) -> str:
        # [3, 7] -> Links zu den Meldungen
        def repl(m):
            nums = [int(x) for x in re.findall(r"\d+", m.group(0)) if int(x) in numbered]
            return " ".join(f'<a class="cite" href="#s{n}">{n}</a>' for n in nums)
        return re.sub(r"\[[\d,\s]+\]", repl, e(line))

    by_topic: dict[str, list[tuple[int, Story]]] = {}
    for n, s in numbered.items():
        by_topic.setdefault(s.topic, []).append((n, s))
    topic_order = sorted(by_topic, key=lambda t: (t == "Weitere Themen", -sum(len(s.sources) for _, s in by_topic[t])))

    parts = []
    if report.summary:
        parts.append('<section class="card summary"><h2>Das Wichtigste in Kürze</h2><ul>'
                     + "".join(f"<li>{cite(l)}</li>" for l in report.summary)
                     + '</ul><p class="note">KI-Zusammenfassung aus Schlagzeilen und Teasern – vor Weiterverwendung prüfen.</p></section>')
    top = [(n, s) for n, s in numbered.items() if len(s.sources) >= 2][:5]
    if top:
        parts.append('<section class="card"><h2>Meistberichtet</h2><ol class="top">'
                     + "".join(f'<li><a href="#s{n}">{e(s.lead.title)}</a> <span class="badge">{len(s.sources)} Medien</span></li>' for n, s in top)
                     + "</ol></section>")
    if report.parlament:
        parts.append('<section class="card"><h2>Grosser Rat BS – neue Geschäfte</h2><ul class="plain">'
                     + "".join(f'<li><a href="{e(p.link)}" target="_blank" rel="noopener">{e(p.title)}</a>'
                               f'<div class="meta">{e(p.teaser)} · {fmt_time(p.published)[:6]}</div></li>' for p in report.parlament)
                     + "</ul></section>")

    nav = "".join(f'<a href="#t{i}">{e(t)} <span>{len(by_topic[t])}</span></a>' for i, t in enumerate(topic_order))
    for i, t in enumerate(topic_order):
        rows = []
        for n, s in by_topic[t]:
            lead = s.lead
            others = [x for x in s.items if x is not lead]
            more = ""
            if others:
                more = ('<details><summary>' + (f"{len(others)} weitere Berichte" if len(others) > 1 else "1 weiterer Bericht") + "</summary><ul>"
                        + "".join(f'<li><a href="{e(o.link)}" target="_blank" rel="noopener">{e(o.title)}</a> <span class="src">{e(o.source)}</span></li>' for o in others)
                        + "</ul></details>")
            rows.append(
                f'<article id="s{n}"><div class="num">{n}</div><div>'
                f'<a class="headline" href="{e(lead.link)}" target="_blank" rel="noopener">{e(lead.title)}</a>'
                + (f'<p>{e(lead.teaser)}</p>' if lead.teaser else "")
                + f'<div class="meta">{e(", ".join(s.sources))} · {fmt_time(s.latest)}</div>{more}</div></article>')
        parts.append(f'<section class="card" id="t{i}"><h2>{e(t)}</h2>{"".join(rows)}</section>')

    if not report.stories and not report.parlament:
        parts.append('<section class="card"><p>Heute keine Meldungen gefunden.</p></section>')
    if report.errors:
        parts.append('<section class="card errors"><h2>Quellen mit Problemen</h2><ul>'
                     + "".join(f"<li>{e(x)}</li>" for x in report.errors) + "</ul></section>")

    arch = " · ".join(f'<a href="archiv/{d}.html">{d[8:10]}.{d[5:7]}.</a>' for d in archive[:14])
    d = datetime.fromisoformat(report.date)
    title = f"Politik Basel – {d.strftime('%d.%m.%Y')}"
    return f"""<!doctype html>
<html lang="de-CH"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<style>{CSS}</style></head>
<body><header><h1>Politik Basel</h1>
<div class="sub">Briefing vom {d.strftime('%d.%m.%Y')} · {len(report.stories)} Themen aus den letzten 24 h · Stand {datetime.now(TZ).strftime('%H:%M')}</div>
<nav>{nav}</nav></header>
<main>{''.join(parts)}</main>
<footer>Archiv: {arch or '–'}<br>Quellen: Google News (diverse Medien), data.bs.ch (Grosser Rat Basel-Stadt).</footer>
</body></html>"""


CSS = """
:root{--bg:#f6f5f2;--card:#fff;--fg:#1c1c1c;--muted:#6b6b6b;--line:#e6e3dc;--accent:#b3001b;--soft:#fbeef0}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--card:#1e1e1e;--fg:#ececec;--muted:#9a9a9a;--line:#2e2e2e;--accent:#ff5a6e;--soft:#2a1a1d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header,main,footer{max-width:820px;margin:0 auto;padding:0 16px}
header{padding-top:24px}h1{margin:0;font-size:28px;letter-spacing:-.02em}h1::before{content:"";display:inline-block;width:12px;height:12px;background:var(--accent);margin-right:10px;vertical-align:middle}
.sub{color:var(--muted);font-size:14px;margin:4px 0 12px}
nav{display:flex;gap:6px;overflow-x:auto;padding-bottom:12px}nav a{white-space:nowrap;font-size:13px;padding:4px 10px;border:1px solid var(--line);border-radius:99px;color:var(--fg);text-decoration:none;background:var(--card)}nav a span{color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 14px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin:0 0 10px}
.summary{background:var(--soft);border-color:transparent}.summary li{margin-bottom:8px}.note{font-size:12px;color:var(--muted);margin:8px 0 0}
a{color:inherit}.cite{font-size:11px;text-decoration:none;background:var(--accent);color:#fff;border-radius:99px;padding:0 6px;margin-left:2px;vertical-align:1px}
article{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line)}article:first-of-type{border-top:0}
.num{flex:0 0 22px;font-size:12px;color:var(--muted);padding-top:3px}
.headline{font-weight:600;text-decoration:none}.headline:hover{text-decoration:underline}
article p{margin:4px 0 0;font-size:14px}.meta,.src{font-size:12px;color:var(--muted);margin-top:4px}
details{font-size:13px;margin-top:4px}summary{cursor:pointer;color:var(--muted)}details ul{padding-left:18px;margin:4px 0}
.top li{margin-bottom:6px}.badge{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:99px;padding:0 6px}
.plain{list-style:none;padding:0;margin:0}.plain li{padding:6px 0;border-top:1px solid var(--line)}.plain li:first-child{border-top:0}
.errors{font-size:13px;color:var(--muted)}footer{color:var(--muted);font-size:12px;padding-bottom:40px}
"""


# ---------------------------------------------------------------- Main

def build(media: list[Item], parlament: list[Item], errors: list[str], use_claude: bool = True) -> Report:
    report = Report(date=datetime.now(TZ).date().isoformat(), errors=errors)
    stories = cluster(within_window(media, 30))
    for s in stories:
        s.topic = classify(s)
    # Wichtigkeit: Anzahl Medien, dann Aktualität
    stories.sort(key=lambda s: (len(s.sources), s.latest or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    report.stories = stories
    report.parlament = parlament
    if use_claude:
        report.summary = summarize(stories, parlament, errors)
    return report


def write(report: Report) -> Path:
    (DOCS / "archiv").mkdir(parents=True, exist_ok=True)
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    archive = sorted({p.stem for p in (DOCS / "archiv").glob("*.html")} | {report.date}, reverse=True)
    page = render(report, archive)
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / "archiv" / f"{report.date}.html").write_text(
        page.replace('href="archiv/', 'href="'), encoding="utf-8")
    (DOCS / "data" / f"{report.date}.json").write_text(
        json.dumps(asdict(report), default=str, ensure_ascii=False, indent=1), encoding="utf-8")
    return DOCS / "index.html"


def main() -> int:
    errors: list[str] = []
    media = fetch_media(errors)
    parlament = fetch_grosser_rat(errors)
    report = build(media, parlament, errors)
    path = write(report)
    print(f"{len(report.stories)} Themen, {len(parlament)} Geschäfte, "
          f"Zusammenfassung: {'ja' if report.summary else 'nein'}, Fehler: {len(errors)} -> {path}")
    for err in errors:
        print("  !", err)
    # Fehlschlagen nur, wenn gar nichts kam (dann sieht man es in GitHub Actions)
    return 0 if (media or parlament) else 1


if __name__ == "__main__":
    sys.exit(main())
