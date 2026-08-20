from typing import List
import requests

from app.config import OLLAMA_URL, OLLAMA_MODEL


class LLMRefiner:
    def __init__(self):
        self.url = OLLAMA_URL
        self.model = OLLAMA_MODEL

    def refine_segment(
        self,
        text: str,
        language: str,
        context: str = "",
    ) -> str:

        prompt = f"""
You are a transcript correction assistant.

The transcript was produced by automatic speech recognition.

Language: {language}

Your job is ONLY to correct obvious ASR errors.

Rules:
1. Preserve the original meaning.
2. Do not add information.
3. Do not summarize.
4. Do not translate.
5. Preserve names, numbers and technical terms.
6. Preserve agricultural terminology.
7. Fix obvious spelling/transcription mistakes.
8. Add natural punctuation where appropriate.
9. Return ONLY the corrected transcript.

Previous context:
{context}

Transcript:
{text}
"""

        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                },
            },
            timeout=120,
        )

        response.raise_for_status()

        result = response.json()

        cleaned = result.get("response", "").strip()

        return cleaned or text

    def refine_segments(
        self,
        segments: List[dict],
        language: str,
    ) -> List[dict]:

        refined = []

        previous_text = ""

        for segment in segments:

            corrected = self.refine_segment(
                segment["text"],
                language,
                previous_text,
            )

            refined_segment = {
                **segment,
                "text": corrected,
            }

            refined.append(refined_segment)

            previous_text = corrected

        return refined