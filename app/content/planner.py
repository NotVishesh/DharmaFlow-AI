"""
DharmaFlow AI — Content Planner
Plans video topics according to the configured category distribution:
  - 30% Scripture Explainers (Bhagavad Gita, Upanishads)
  - 25% Epic Storytelling (Ramayana, Mahabharata)
  - 20% Devotional Reflections
  - 15% Festivals and Cultural Observances
  - 10% Temple and Historical Explainers
"""
from __future__ import annotations

import logging
import random
from typing import Optional

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.database.models import ContentCategory, ContentIdea, Script

logger = logging.getLogger(__name__)

CURATED_TOPIC_POOL: dict[str, list[dict[str, str]]] = {
    ContentCategory.GENERAL.value: [
        {
            "topic": "How Submarine Fiber Optic Cables Power 99% of the Global Internet",
            "language": "en",
            "source_hint": "TeleGeography Submarine Cable Map & Optical Engineering",
        },
        {
            "topic": "The 5-Second Rule: How to Beat Procrastination Instantly",
            "language": "en",
            "source_hint": "Behavioral Psychology & Prefrontal Cortex Activation",
        },
    ],
    ContentCategory.TECH_AI.value: [
        {
            "topic": "How Large Language Models Actually Predict the Next Word",
            "language": "en",
            "source_hint": "Transformer Architecture (Vaswani et al., Attention Is All You Need)",
        },
        {
            "topic": "Quantum Computing Explained in 45 Seconds",
            "language": "en",
            "source_hint": "Qubits, Superposition & Entanglement in Quantum Mechanics",
        },
    ],
    ContentCategory.SCIENCE_SPACE.value: [
        {
            "topic": "What Happens If You Fall Into a Supermassive Black Hole?",
            "language": "en",
            "source_hint": "General Relativity, Event Horizon & Spaghettification",
        },
        {
            "topic": "Why Time Moves Slower Near Massive Objects — Time Dilation",
            "language": "en",
            "source_hint": "Einstein's Theory of General Relativity",
        },
    ],
    ContentCategory.MOTIVATION_MINDSET.value: [
        {
            "topic": "The Power of Atomic Habits: Getting 1% Better Every Day",
            "language": "en",
            "source_hint": "Compound Growth in Behavioral Habit Formation",
        },
        {
            "topic": "Stoic Philosophy: Focusing Only on What You Can Control",
            "language": "en",
            "source_hint": "Marcus Aurelius — Meditations & Epictetus",
        },
    ],
    ContentCategory.HISTORY_CULTURE.value: [
        {
            "topic": "How the Library of Alexandria Changed Human Civilization",
            "language": "en",
            "source_hint": "Ancient Hellenistic History & Scholarship",
        },
        {
            "topic": "The Unbelievable Engineering of the Roman Aqueducts",
            "language": "en",
            "source_hint": "Ancient Roman Civil Engineering",
        },
    ],
    ContentCategory.FINANCE_BUSINESS.value: [
        {
            "topic": "The 8th Wonder of the World: How Compound Interest Builds Wealth",
            "language": "en",
            "source_hint": "Exponential Financial Mathematics",
        },
        {
            "topic": "Why Inflation Silently Erodes Purchasing Power Over Time",
            "language": "en",
            "source_hint": "Macroeconomics & Monetary Policy",
        },
    ],
    ContentCategory.STORYTELLING.value: [
        {
            "topic": "The Parable of the Bamboo Tree: Patience Before the Breakthrough",
            "language": "en",
            "source_hint": "Inspirational Storytelling & Growth Mindset",
        },
    ],
    ContentCategory.FACTS_TRIVIA.value: [
        {
            "topic": "3 Mind-Blowing Facts About the Deep Ocean You Didn't Know",
            "language": "en",
            "source_hint": "NOAA Oceanography & Marine Biology",
        },
    ],
    ContentCategory.HEALTH_PSYCHOLOGY.value: [
        {
            "topic": "How Morning Sunlight Resets Your Circadian Rhythm and Focus",
            "language": "en",
            "source_hint": "Neurobiology & Circadian Neuroscience",
        },
    ],
    ContentCategory.PHILOSOPHY_WISDOM.value: [
        {
            "topic": "Finding Inner Strength: Teachings of Swami Vivekananda",
            "language": "en",
            "source_hint": "Complete Works of Swami Vivekananda",
        },
    ],
    ContentCategory.SCRIPTURE_EXPLAINER.value: [
        {
            "topic": "Bhagavad Gita 2:47 — The True Essence of Karma Yoga",
            "language": "hi",
            "source_hint": "Gita 2:47 (Karmanye Vadhikaraste)",
        },
        {
            "topic": "Bhagavad Gita 2:20 — The Soul Can Never Be Destroyed",
            "language": "hi",
            "source_hint": "Gita 2:20 (Na Jayate Mriyate Va)",
        },
        {
            "topic": "Isha Upanishad Shloka 1 — Everything Belongs to the Divine",
            "language": "en",
            "source_hint": "Isha Upanishad (Ishavasyam Idam Sarvam)",
        },
        {
            "topic": "Bhagavad Gita 4:7 — When Righteousness Declines, I Manifest",
            "language": "hi",
            "source_hint": "Gita 4:7 (Yada Yada Hi Dharmasya)",
        },
        {
            "topic": "Bhagavad Gita 9:22 — The Promise of Divine Protection",
            "language": "hi",
            "source_hint": "Gita 9:22 (Ananyash Chintayanto Mam)",
        },
    ],
    ContentCategory.EPIC_STORYTELLING.value: [
        {
            "topic": "Why Lakshmana Stayed Awake for 14 Years in Exile",
            "language": "hi",
            "source_hint": "Valmiki Ramayana / Traditional folk retelling of Urmila and Nidra Devi",
        },
        {
            "topic": "The Wisdom of Vidura — Vidura Niti on True Wealth",
            "language": "hi-en",
            "source_hint": "Mahabharata, Udyoga Parva (Vidura Niti)",
        },
        {
            "topic": "Karna and Krishna's Final Conversation on Dharma",
            "language": "hi",
            "source_hint": "Mahabharata, Karna Parva",
        },
        {
            "topic": "Jatayu's Ultimate Sacrifice for Sita",
            "language": "hi",
            "source_hint": "Valmiki Ramayana, Aranya Kanda",
        },
    ],
    ContentCategory.DEVOTIONAL_REFLECTION.value: [
        {
            "topic": "The Deep Meaning of the Mahamrityunjaya Mantra",
            "language": "hi",
            "source_hint": "Rigveda 7.59.12 / Shiva Purana",
        },
        {
            "topic": "Hanuman Chalisa: Why Fear Vanishes with Hanuman's Name",
            "language": "hi",
            "source_hint": "Goswami Tulsidas, Hanuman Chalisa (Verse 24-25)",
        },
        {
            "topic": "The Power of Surrender (Sharanagati) in Bhakti",
            "language": "en",
            "source_hint": "Bhagavad Gita 18:66 (Sarva Dharman Parityajya)",
        },
        {
            "topic": "Why Hindus Light Diyas at Sunset — Spiritual Significance",
            "language": "hi",
            "source_hint": "Traditional Agni Upasana symbolism",
        },
    ],
    ContentCategory.FESTIVAL_CULTURAL.value: [
        {
            "topic": "The Real Story Behind Diwali — Beyond Firecrackers",
            "language": "hi",
            "source_hint": "Ramayana Ayodhya return & Skanda Purana deepavali tradition",
        },
        {
            "topic": "Nine Forms of Goddess Durga during Navaratri Explained",
            "language": "hi",
            "source_hint": "Devi Mahatmya / Markandeya Purana",
        },
        {
            "topic": "Maha Shivaratri — The Night of Spiritual Awakening",
            "language": "hi",
            "source_hint": "Shiva Purana, Kotirudra Samhita",
        },
        {
            "topic": "The Significance of Ekadashi Fasting in Hindu Tradition",
            "language": "en",
            "source_hint": "Padma Purana, Ekadashi Mahatmya",
        },
    ],
    ContentCategory.TEMPLE_HISTORICAL.value: [
        {
            "topic": "The Architectural Mystery of Kailasa Temple, Ellora",
            "language": "hi",
            "source_hint": "Rashtrakuta dynasty 8th century cave 16 historical record",
        },
        {
            "topic": "The Mystery of Puri Jagannath Temple Flags and Breeze",
            "language": "hi",
            "source_hint": "Jagannath Temple tradition / Sthala Purana",
        },
        {
            "topic": "Thanjavur Brihadisvara Temple — Chola Architectural Marvel",
            "language": "en",
            "source_hint": "Rajaraja Chola I inscription (1010 CE)",
        },
    ],
}


class ContentPlanner:
    """Plans upcoming content by balancing category distribution."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def select_next_category(self) -> str:
        """Select the next category balancing towards target distribution."""
        target_dist = self.settings.content.category_distribution

        # Count published or generated scripts per category
        total_scripts = self.db.query(Script).count()
        if total_scripts == 0:
            categories = list(target_dist.keys())
            weights = list(target_dist.values())
            return random.choices(categories, weights=weights, k=1)[0]

        # Calculate shortfall for each category
        shortfalls: dict[str, float] = {}
        for cat, target_ratio in target_dist.items():
            count = self.db.query(Script).filter(Script.category == cat).count()
            actual_ratio = count / total_scripts
            shortfalls[cat] = target_ratio - actual_ratio

        # Pick category with greatest shortfall
        best_category = max(shortfalls, key=shortfalls.get)
        logger.info("Category planner selected '%s' (shortfall: %.2f)", best_category, shortfalls[best_category])
        return best_category

    def get_or_create_next_idea(self) -> ContentIdea:
        """Fetch the next unused backlog idea or generate one from the curated pool."""
        # 1. Look for manual backlog ideas in DB
        unused = self.db.query(ContentIdea).filter(ContentIdea.used == False).order_by(ContentIdea.priority.desc()).first()
        if unused:
            return unused

        # 2. Pick a balanced category
        cat = self.select_next_category()
        pool = CURATED_TOPIC_POOL.get(cat, CURATED_TOPIC_POOL[ContentCategory.SCRIPTURE_EXPLAINER.value])

        # Find an item from pool not yet generated
        existing_topics = set(s.topic.lower() for s in self.db.query(Script.topic).all())
        candidates = [item for item in pool if item["topic"].lower() not in existing_topics]

        if not candidates:
            candidates = pool

        chosen = random.choice(candidates)
        new_idea = ContentIdea(
            topic=chosen["topic"],
            category=cat,
            language=chosen.get("language", "hi"),
            source_hint=chosen.get("source_hint"),
            priority=5,
            used=False,
        )
        self.db.add(new_idea)
        self.db.commit()
        self.db.refresh(new_idea)
        logger.info("ContentPlanner created new planned idea: %s", new_idea.topic)
        return new_idea
