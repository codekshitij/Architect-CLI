import time
import re
import os
import json

import requests
from requests import RequestException

class InferenceEngine:
    def __init__(
        self,
        model="qwen2.5-coder:7b",
        timeout=10,
        max_retries=2,
        retry_backoff_seconds=1.0,
    ):
        self.url = "http://localhost:11434/api/generate"
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.cache_salt = "label_policy_v4_detailed_clean"

    def _fallback_from_hint(self, file_a, file_b, hint):
        source_name = os.path.splitext(os.path.basename(file_a))[0]
        target_name = os.path.splitext(os.path.basename(file_b))[0]
        if hint:
            return f"{hint} for {target_name} integration in {source_name}"
        return f"uses {target_name} for {source_name} runtime integration"

    def _normalize_label(self, label, file_a, file_b, hint=""):
        text = str(label or "").strip().replace('"', "'")

        # Handle model responses that include extra prose or markdown fences.
        text = text.replace("```json", "").replace("```", "").strip()
        if text.startswith("{") and "label" in text:
            try:
                payload = json.loads(text)
                text = str(payload.get("label", "")).strip()
            except (ValueError, TypeError):
                pass

        # Keep the first line if model returned a paragraph.
        text = text.splitlines()[0].strip()
        text = text.lower()

        # Remove common LLM artifacts such as leading "label" tokens.
        text = re.sub(r"\blabel", "", text)
        text = re.sub(r"\b([a-z0-9_]+)\.py\b", r"\1", text)
        text = re.sub(r"\b([a-z0-9_]+)py\b", r"\1", text)

        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-zA-Z0-9\s\-_/]", "", text)
        text = text.strip("- ")

        generic_markers = [
            "file a",
            "file b",
            "financial analysis",
            "provides tools",
            "defined in",
            "tasks",
            "relationship",
        ]
        is_generic = any(marker in text.lower() for marker in generic_markers)

        words = text.split()
        if not text or len(words) < 5 or len(words) > 14 or is_generic:
            return self._fallback_from_hint(file_a, file_b, hint)

        if hint:
            hint_tokens = [p for p in hint.split() if p not in {"imports", "from", "includes", "uses"}]
            if hint_tokens and all(token.lower() not in text.lower() for token in hint_tokens):
                return self._fallback_from_hint(file_a, file_b, hint)

        return text

    def get_relationship(self, file_a, code_a, file_b, code_b, hint=""):
        # Truncate code to 1000 chars each for speed/context limits
        prompt = (
            f"File A: {file_a}\nCode Snippet: {code_a[:1000]}\n\n"
            f"File B: {file_b}\nCode Snippet: {code_b[:1000]}\n\n"
            f"Observed dependency hint: {hint or 'uses target module'}\n\n"
            "File A references/imports File B. Return ONLY JSON: "
            '{"label":"<detailed relationship>"}. '
            "Label rules: 7-12 words, concrete technical wording, include the target module name, "
            "describe purpose in code terms, no mentions of File A/File B, no generic business phrases."
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "system": (
                "You are an expert software architecture analyst. "
                "Return only valid JSON with a single key named label. "
                "Use specific implementation-level relationship text and avoid generic statements."
            ),
            "options": {
                "temperature": 0.15,
                "num_predict": 60,
            },
        }

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(self.url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                label = response.json().get("response", "dependency")
                return self._normalize_label(label, file_a, file_b, hint)
            except (RequestException, ValueError):
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * (attempt + 1))

        return self._fallback_from_hint(file_a, file_b, hint)