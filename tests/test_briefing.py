"""Offline-Tests mit Beispieldaten: python -m pytest tests  (oder: python tests/test_briefing.py)"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import briefing

NOW = datetime.now(timezone.utc)

RSS = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Grosser Rat genehmigt Budget 2027 mit Überschuss - bz Basel</title><link>https://a/1</link>
<pubDate>{(NOW - timedelta(hours=2)).strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate><source url="https://bz">bz Basel</source></item>
<item><title>Budget 2027: Grosser Rat sagt Ja zum Überschuss - Basler Zeitung</title><link>https://a/2</link>
<pubDate>{(NOW - timedelta(hours=3)).strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate><source url="https://baz">Basler Zeitung</source></item>
<item><title>Landrat streitet über Tramlinie nach Allschwil - Prime News</title><link>https://a/3</link>
<pubDate>{(NOW - timedelta(hours=5)).strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate><source url="https://p">Prime News</source></item>
<item><title>Alte Meldung über Fasnacht - SRF</title><link>https://a/4</link>
<pubDate>{(NOW - timedelta(days=5)).strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate><source url="https://s">SRF</source></item>
</channel></rss>""".encode()


def test_pipeline(tmp_path=None):
    items = briefing.parse_feed(RSS, "Google News")
    assert items[0].source == "bz Basel" and not items[0].title.endswith("bz Basel")
    parl = [briefing.Item("Anzug betreffend Velowege", "https://gr", "Grosser Rat BS",
                          NOW, "25.5123 · Anzug", "parlament")]
    report = briefing.build(items, parl, ["Testquelle: Timeout"], use_claude=False)
    assert len(report.stories) == 2, [s.lead.title for s in report.stories]  # Duplikat zusammengeführt, alte Meldung raus
    top = report.stories[0]
    assert top.sources == ["Basler Zeitung", "bz Basel"]
    assert top.topic == "Finanzen & Steuern"
    assert report.stories[1].topic == "Verkehr & Mobilität"
    report.summary = ["Der Grosse Rat genehmigt das Budget [1]", "Streit um Tram <script> [2, 99]"]
    page = briefing.render(report, [report.date])
    assert "<script>" not in page and 'href="#s1"' in page and "Meistberichtet" in page
    out = Path(tmp_path or "/tmp") / "preview.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    print("OK ->", test_pipeline(sys.argv[1] if len(sys.argv) > 1 else None))
