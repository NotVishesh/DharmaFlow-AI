"""
DharmaFlow AI — LLM Provider Interface
Abstract base + concrete implementations for local (Ollama) and cloud LLMs.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7,
                 max_tokens: int = 4096) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def generate_json(self, prompt: str, system_prompt: str = "",
                      max_attempts: int = 3, **kwargs) -> dict | list:
        """Generate and parse JSON, retrying on parse failure."""
        for attempt in range(1, max_attempts + 1):
            raw = self.generate(prompt, system_prompt, **kwargs)
            try:
                # Strip markdown code fences if present
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.warning("JSON parse failed (attempt %d/%d): %s", attempt, max_attempts, e)
                if attempt == max_attempts:
                    raise ValueError(f"LLM returned invalid JSON after {max_attempts} attempts: {raw[:200]}")
        return {}


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434",
                 temperature: float = 0.7, max_tokens: int = 4096, timeout: int = 120):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7,
                 max_tokens: int = 4096) -> str:
        import httpx
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        start = time.time()
        try:
            r = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
            elapsed = time.time() - start
            result = r.json().get("response", "")
            logger.debug("Ollama generated %d chars in %.1fs", len(result), elapsed)
            return result
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama request failed: {e}") from e


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 temperature: float = 0.7, max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7,
                 max_tokens: int = 4096) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        client = OpenAI(api_key=self.api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022",
                 temperature: float = 0.7, max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7,
                 max_tokens: int = 4096) -> str:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(**kwargs)
        return response.content[0].text


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash",
                 temperature: float = 0.7, max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7,
                 max_tokens: int = 4096) -> str:
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")
        genai.configure(api_key=self.api_key)
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        model = genai.GenerativeModel(self.model)
        config = genai.types.GenerationConfig(
            temperature=temperature, max_output_tokens=max_tokens
        )
        response = model.generate_content(full_prompt, generation_config=config)
        return response.text


class MockLLMProvider(LLMProvider):
    """Offline mock LLM for tests and demo mode. Returns deterministic topic-aware content."""

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        import re
        topic_match = re.search(r"Topic:\s*(.+)", prompt)
        cat_match = re.search(r"Category:\s*(.+)", prompt)
        lang_match = re.search(r"\(code:\s*([a-zA-Z\-]+)\)", prompt)
        dur_match = re.search(r"Target Duration:\s*(\d+)", prompt)

        topic = topic_match.group(1).strip() if topic_match else ""
        category = cat_match.group(1).strip() if cat_match else "scripture_explainer"
        language = lang_match.group(1).strip() if lang_match else "hi"
        duration = int(dur_match.group(1)) if dur_match else 40

        if topic and "bhagavad gita" not in topic.lower() and category != "scripture_explainer":
            return json.dumps(self._universal_script(topic, category, language, duration))
        if topic and language == "en":
            return json.dumps(self._universal_script(topic, category, language, duration))
        return json.dumps(self._demo_script())

    def _universal_script(self, topic: str, category: str, language: str, duration: int) -> dict:
        scene_dur = max(3.0, round(duration / 3.0, 1))
        return {
            "topic": topic,
            "category": category,
            "language": language,
            "target_duration_seconds": duration,
            "title_options": [
                f"{topic[:70]} — Explained",
                f"The Fascinating Truth About {topic[:60]}",
                f"Understanding {topic[:75]}",
            ],
            "opening_hook": f"Have you ever wondered how {topic} actually works and why it changes everything we know?",
            "narration": (
                f"Have you ever wondered how {topic} actually works? "
                f"At its core, {topic} reveals some of the most fascinating principles in {category.replace('_', ' ')}. "
                f"Every detail connects together to shape our understanding of the world and the future ahead."
            ),
            "scenes": [
                {
                    "scene_number": 1,
                    "narration_text": f"Have you ever wondered how {topic} actually works and why it matters so much today?",
                    "approximate_duration_seconds": scene_dur,
                    "visual_prompt": f"Cinematic wide shot illustrating {topic}, dramatic volumetric lighting, ultra detailed, vertical 9:16 composition",
                    "visual_type": "cinematic",
                    "camera_movement": "slow_zoom_in",
                    "subtitle_text": f"How does {topic[:45]} work?",
                    "source_reference": "Open Educational Reference",
                },
                {
                    "scene_number": 2,
                    "narration_text": f"When we look closely at {topic}, we discover key insights that transform how we see {category.replace('_', ' ')}.",
                    "approximate_duration_seconds": scene_dur,
                    "visual_prompt": f"Detailed close-up visualization of {topic}, glowing depth of field, modern educational aesthetic, vertical 9:16 portrait",
                    "visual_type": "infographic",
                    "camera_movement": "slow_pan_up",
                    "subtitle_text": f"Key insights behind {topic[:40]}",
                    "source_reference": "Encyclopaedia Britannica",
                },
                {
                    "scene_number": 3,
                    "narration_text": f"Mastering these ideas gives us a whole new perspective. Stay curious, like, and subscribe for more.",
                    "approximate_duration_seconds": scene_dur,
                    "visual_prompt": f"Inspiring futuristic horizon representing discovery and knowledge about {topic}, crisp cinematic lighting, vertical 9:16",
                    "visual_type": "futuristic",
                    "camera_movement": "slow_zoom_out",
                    "subtitle_text": "Stay curious — Like & Subscribe",
                    "source_reference": None,
                },
            ],
            "closing_line": f"Understanding {topic} opens the door to deeper curiosity and smarter thinking.",
            "call_to_action": "If you found this insightful, hit Like and Subscribe for daily short-form explainers.",
            "source_references": [
                {
                    "name": "Encyclopaedia Britannica",
                    "url": "https://www.britannica.com/",
                    "source_type": "commentary",
                    "author": "Britannica Editors",
                    "passage": f"Educational overview of {topic}",
                    "license_notes": "Factual reference; original narration and synthesis.",
                }
            ],
            "claims_and_evidence": [
                {
                    "claim_text": f"Core educational overview of {topic}",
                    "claim_type": "educational_fact",
                    "source_name": "Encyclopaedia Britannica",
                    "source_reference": "Encyclopaedia Britannica",
                    "verified": True,
                    "needs_review": False,
                }
            ],
            "copyright_notes": "Original educational script and commentary.",
            "ai_disclosure_required": True,
            "verification_status": "VERIFIED",
        }

    def _demo_script(self) -> dict:
        return {
            "topic": "The Teaching of Equanimity from Bhagavad Gita",
            "category": "scripture_explainer",
            "language": "hi",
            "target_duration_seconds": 40,
            "title_options": [
                "भगवद गीता का संदेश — समभाव",
                "Bhagavad Gita Chapter 2: The Wisdom of Equanimity",
                "कर्म करो, फल की चिंता मत करो",
            ],
            "opening_hook": "क्या आप जानते हैं कि भगवद गीता में अर्जुन के एक प्रश्न ने मानवता को जीने का तरीका बदल दिया?",
            "narration": (
                "महाभारत के कुरुक्षेत्र में, अर्जुन युद्ध से पहले अपने प्रियजनों को देख कर विचलित हो गए। "
                "तब श्री कृष्ण ने उन्हें भगवद गीता का ज्ञान दिया। "
                "अध्याय 2, श्लोक 47 में कृष्ण कहते हैं: "
                "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। "
                "अर्थात् — तुम्हारा अधिकार केवल कर्म पर है, उसके फल पर नहीं। "
                "यह संदेश आज भी उतना ही प्रासंगिक है।"
            ),
            "scenes": [
                {
                    "scene_number": 1,
                    "narration_text": "कुरुक्षेत्र में अर्जुन अपने प्रियजनों को देख विचलित हो गए।",
                    "approximate_duration_seconds": 6.0,
                    "visual_prompt": "Ancient Indian battlefield at sunrise, warrior Arjuna in a chariot looking sorrowful, divine atmosphere, vertical 9:16 composition, soft golden light, classical Indian art style",
                    "visual_type": "illustration",
                    "camera_movement": "slow_zoom_in",
                    "subtitle_text": "कुरुक्षेत्र में अर्जुन विचलित हो गए",
                    "source_reference": "Bhagavad Gita Chapter 1",
                },
                {
                    "scene_number": 2,
                    "narration_text": "श्री कृष्ण ने कहा — कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
                    "approximate_duration_seconds": 8.0,
                    "visual_prompt": "Lord Krishna speaking to Arjuna, divine blue skin, peacock feather crown, glowing aura, Sanskrit text floating in air, sacred atmosphere, vertical portrait orientation, classical Indian painting style",
                    "visual_type": "deity",
                    "camera_movement": "slow_zoom_out",
                    "subtitle_text": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन",
                    "source_reference": "Bhagavad Gita 2:47",
                },
                {
                    "scene_number": 3,
                    "narration_text": "तुम्हारा अधिकार केवल कर्म पर है, फल पर नहीं। यही समभाव का मार्ग है।",
                    "approximate_duration_seconds": 8.0,
                    "visual_prompt": "Peaceful meditating figure in lotus pose, sunrise over Himalayas, serene golden light, spiritual atmosphere, vertical composition, Indian art style",
                    "visual_type": "illustration",
                    "camera_movement": "slow_pan_up",
                    "subtitle_text": "कर्म करो, फल की चिंता मत करो",
                    "source_reference": None,
                },
                {
                    "scene_number": 4,
                    "narration_text": "आज से अपने कार्य में समभाव रखें। लाइक करें और फॉलो करें।",
                    "approximate_duration_seconds": 5.0,
                    "visual_prompt": "Beautiful mandala with Sanskrit Om symbol, warm orange and gold colors, spiritual energy, vertical format, glowing divine light",
                    "visual_type": "abstract",
                    "camera_movement": "slow_zoom_in",
                    "subtitle_text": "समभाव अपनाएं — Like करें और Follow करें",
                    "source_reference": None,
                },
            ],
            "closing_line": "श्री कृष्ण का यह ज्ञान हमें सिखाता है कि सच्ची शांति कर्म में है, फल की चाहत में नहीं।",
            "call_to_action": "अगर यह वीडियो आपको अच्छा लगा, तो Like करें और DharmaFlow को Follow करें।",
            "source_references": [
                {
                    "name": "Bhagavad Gita 2:47",
                    "url": "https://www.gitasupersite.iitk.ac.in/srimad?language=dv&field_chapter_value=2&field_nsutra_value=47",
                    "source_type": "scripture",
                    "author": "Vyasa (traditionally attributed)",
                    "passage": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन",
                    "license_notes": "Ancient scripture; modern translations may be copyrighted separately."
                }
            ],
            "claims_and_evidence": [
                {
                    "claim_text": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन is from Bhagavad Gita Chapter 2, Verse 47",
                    "claim_type": "direct_quotation",
                    "source_name": "Bhagavad Gita 2:47",
                    "source_reference": "Gita Supersite IIT Kanpur",
                    "verified": True,
                    "needs_review": False
                }
            ],
            "copyright_notes": "Sanskrit shloka is ancient scripture (public domain). Hindi narration and commentary are original. No music or third-party media used.",
            "ai_disclosure_required": True,
            "verification_status": "VERIFIED",
        }
