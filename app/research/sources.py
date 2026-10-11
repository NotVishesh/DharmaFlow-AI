"""
DharmaFlow AI — Source Registry
Trusted devotional and academic sources pre-loaded for fact-checking.
"""
from __future__ import annotations

TRUSTED_SOURCES: list[dict] = [
    {
        "name": "Bhagavad Gita As It Is (Prabhupada translation)",
        "url": "https://asitis.com/",
        "source_type": "scripture_translation",
        "author": "A.C. Bhaktivedanta Swami Prabhupada",
        "publisher": "Bhaktivedanta Book Trust",
        "license_notes": "Copyright BBT; fair use for commentary and education. Do not reproduce chapter text wholesale.",
        "reliability_notes": "Widely used ISKCON translation. Other traditions may interpret differently.",
        "is_trusted": True,
    },
    {
        "name": "Gita Supersite (IIT Kanpur)",
        "url": "https://www.gitasupersite.iitk.ac.in/",
        "source_type": "academic_scripture_database",
        "author": "IIT Kanpur",
        "license_notes": "Free for educational use.",
        "reliability_notes": "Provides Sanskrit, transliterations, and multiple commentaries.",
        "is_trusted": True,
    },
    {
        "name": "Valmiki Ramayana (translation by Desiraju Hanumanta Rao)",
        "url": "http://www.valmikiramayan.net/",
        "source_type": "scripture_translation",
        "author": "Desiraju Hanumanta Rao",
        "license_notes": "Content available for educational non-commercial use.",
        "reliability_notes": "Verse-by-verse translation. Note: different Ramayana versions exist.",
        "is_trusted": True,
    },
    {
        "name": "Srimad Bhagavatam (Vedabase)",
        "url": "https://vedabase.io/en/library/sb/",
        "source_type": "scripture_translation",
        "author": "A.C. Bhaktivedanta Swami Prabhupada",
        "publisher": "Bhaktivedanta Book Trust",
        "license_notes": "Copyright BBT. Use for commentary and education.",
        "is_trusted": True,
    },
    {
        "name": "Sacred Texts Archive — Hindu Texts",
        "url": "https://www.sacred-texts.com/hin/",
        "source_type": "public_domain_archive",
        "license_notes": "Many texts are public domain translations. Verify each text individually.",
        "reliability_notes": "Contains older translations which may differ from modern scholarship.",
        "is_trusted": True,
    },
    {
        "name": "Sanskrit Documents (sanskritdocuments.org)",
        "url": "https://sanskritdocuments.org/",
        "source_type": "scripture_database",
        "license_notes": "Free for educational use.",
        "reliability_notes": "Devanagari text files; useful for exact verse verification.",
        "is_trusted": True,
    },
    {
        "name": "Drik Panchang",
        "url": "https://www.drikpanchang.com/",
        "source_type": "festival_calendar",
        "reliability_notes": "Widely used Hindu calendar with regional variations. Always verify the year and region.",
        "is_trusted": True,
    },
    {
        "name": "Journal of Hindu Studies (Oxford Academic)",
        "url": "https://academic.oup.com/jhs",
        "source_type": "peer_reviewed_journal",
        "publisher": "Oxford University Press",
        "license_notes": "Paywall for most content. Use for citation purposes.",
        "is_trusted": True,
    },
]


def get_source_by_name(name: str) -> dict | None:
    for src in TRUSTED_SOURCES:
        if src["name"].lower() == name.lower():
            return src
    return None


def list_sources_by_type(source_type: str) -> list[dict]:
    return [s for s in TRUSTED_SOURCES if s.get("source_type") == source_type]
