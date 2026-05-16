from __future__ import annotations

import os

from openai import OpenAI

from .base import BaseQuery, DictWord

_SYSTEM_PROMPT = """
You are a professional dictionary assistant. User will provide the word or phrase in {source_lang}.
You need to provide a comprehensive explanation including {source_lang} pronunciation, definitions, and example sentences using {target_lang} as the target language.
Return only JSON that matches this shape:
{{
  "text": "dictionary headword",
  "pronounce": "pronunciation or reading",
  "explanations": [
    {{
      "text": "definition in {target_lang}",
      "examples": [
        {{
          "original_text": "example sentence in the source language",
          "translated_text": "example translation in {target_lang}"
        }}
      ]
    }}
  ]
}}
"""

_USER_PROMPT = """
Word: {word}
Source language: {source_lang}
Target language: {target_lang}
"""

class OpenAIQuery(BaseQuery):
    name = 'OpenAI'

    def __init__(
        self,
        model: str | None = None,
        entrypoint: str = 'http://localhost:8080/v1',
        api_key: str | None = None,
        source_lang: str = "Japanese",
        target_lang: str = "Simplified Chinese",
        temperature = 0.2,
        persistent_context: bool = True,
    ) -> None:
        self.model = model
        self.entrypoint = entrypoint
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.temperature = temperature
        self.persistent_context = persistent_context
        self._messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        self._client = OpenAI(base_url=entrypoint, api_key=self.api_key) if self.api_key else None

    def is_loaded(self) -> bool:
        return self._client is not None

    def query(self, text: str) -> DictWord:
        if not self._client:
            raise RuntimeError(
                "OpenAI client is not loaded. Provide api_key or set OPENAI_API_KEY."
            )

        user_message = {
            "role": "user",
            "content": _USER_PROMPT.format(
                word=text,
                source_lang=self.source_lang,
                target_lang=self.target_lang,
            ),
        }
        messages = (
            [*self._messages, user_message]
            if self.persistent_context
            else [
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(
                        word=text,
                        source_lang=self.source_lang,
                        target_lang=self.target_lang,
                    ),
                },
                user_message,
            ]
        )

        response = self._client.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=DictWord,
            temperature=self.temperature
        )

        message = response.choices[0].message
        if message.parsed is None:
            raise ValueError(f"OpenAI returned an invalid dictionary response for: {text}")

        if self.persistent_context:
            self._messages.extend(
                [
                    user_message,
                    {
                        "role": "assistant",
                        "content": message.content or message.parsed.model_dump_json(),
                    },
                ]
            )

        return message.parsed
