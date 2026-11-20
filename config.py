"""Konfiguration: Quellen und Themen. Hier anpassen, ohne den Code anzufassen."""

# Google-News-Suchfeeds. Decken BaZ, bz, Prime News, Bajour, SRF, Telebasel u. a. ab.
# "when:1d" = nur die letzten 24 Stunden.
GOOGLE_NEWS_QUERIES = [
    'Basel Politik when:1d',
    '"Grosser Rat" Basel when:1d',
    '"Regierungsrat" Basel-Stadt when:1d',
    'Landrat Baselland when:1d',
    'Regierungsrat Baselland when:1d',
    'Basel Abstimmung OR Initiative OR Referendum when:1d',
    'Basel Nationalrat OR Ständerat OR Bundesrat when:1d',
]

# Direkte RSS-Feeds (optional). Format: ("Name", "URL").
# Feeds, die nicht antworten, werden übersprungen und im Briefing als Fehler gezeigt.
DIRECT_FEEDS: list[tuple[str, str]] = [
    # ("bz Basel", "https://..."),
]

# Grosser Rat Basel-Stadt – Open Data (data.bs.ch, Datensatz 100311 «Geschäfte»)
GROSSER_RAT_DATASET = "100311"
GROSSER_RAT_DAYS = 7  # Parlamentsgeschäfte der letzten N Tage

# Themen: Stichwörter (klein geschrieben, Wortanfang genügt).
TOPICS = {
    "Verkehr & Mobilität": ["verkehr", "tram", "bvb", "blt", "velo", "parkpl", "strasse", "autobahn", "rheintunnel", "bahn", "sbb", "herzstück", "flughafen", "euroairport"],
    "Finanzen & Steuern": ["steuer", "budget", "finanz", "defizit", "überschuss", "rechnung", "sparpaket", "franken"],
    "Wohnen & Stadtentwicklung": ["wohn", "miete", "bau", "areal", "klybeck", "dreispitz", "stadtentwicklung", "zonenplan", "immobil"],
    "Bildung": ["schul", "bildung", "universität", "uni basel", "lehr", "kita", "fhnw", "gymnas"],
    "Gesundheit & Soziales": ["spital", "gesundheit", "usb", "kantonsspital", "prämie", "pflege", "sozialhilfe", "armut", "rente", "ahv"],
    "Umwelt & Energie": ["klima", "energie", "iwb", "solar", "umwelt", "rhein", "fernwärme", "netto-null", "co2"],
    "Sicherheit & Justiz": ["polizei", "gericht", "staatsanwalt", "kriminal", "sicherheit", "demo", "strafe"],
    "Wirtschaft & Arbeit": ["wirtschaft", "novartis", "roche", "pharma", "arbeit", "lohn", "stellen", "messe", "unternehm", "handelskammer"],
    "Kultur & Gesellschaft": ["kultur", "museum", "theater", "fasnacht", "esc", "sport", "fcb", "kunst", "art basel"],
    "Wahlen & Abstimmungen": ["wahl", "abstimm", "initiative", "referendum", "kandid", "partei", "sp ", "svp", "fdp", "grüne", "glp", "mitte", "ldp", "basta"],
    "Partnerschaft BS/BL & Region": ["fusion", "partnerschaft", "baselland", "baselbiet", "liestal", "trinational", "grenzgänger", "lörrach", "mulhouse", "elsass"],
}

# Claude-Zusammenfassung (nur aktiv, wenn ANTHROPIC_API_KEY gesetzt ist)
CLAUDE_MODEL = "claude-opus-5-5"
MAX_ITEMS_FOR_SUMMARY = 60
