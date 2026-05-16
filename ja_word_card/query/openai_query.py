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
"""


class OpenAIQuery(BaseQuery):
    name = "OpenAI"

    def __init__(
        self,
        model: str | None = None,
        entrypoint: str = "http://localhost:8080/v1",
        api_key: str | None = None,
        source_lang: str = "Japanese",
        target_lang: str = "Simplified Chinese",
        temperature=0.5,
        is_multi_model: bool = False,
    ) -> None:
        self.model = model
        self.entrypoint = entrypoint
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.temperature = temperature
        self.is_multi_model = is_multi_model
        self._system_prompt = _SYSTEM_PROMPT.format(
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )
        self._messages = [
            {
                "role": "system",
                "content": (
                    self._system_prompt
                    if not self.is_multi_model
                    else [
                        {
                            "type": "text",
                            "text": self._system_prompt,
                        }
                    ]
                ),
            }
        ]
        try:
            self._client = OpenAI(base_url=entrypoint, api_key=self.api_key)
        except:
            self._client = None

    def is_loaded(self) -> bool:
        return self._client is not None

    def query(self, text: str) -> DictWord:
        if not self._client:
            raise RuntimeError("OpenAI client is not loaded.")
        user_prompt = _USER_PROMPT.format(
            word=text,
        )
        user_message = {
            "role": "user",
            "content": (
                user_prompt
                if not self.is_multi_model
                else [
                    {
                        "type": "text",
                        "text": user_prompt,
                    }
                ]
            ),
        }
        self._messages.append(user_message)
        response = self._client.chat.completions.parse(
            model=self.model,
            messages=self._messages,
            response_format=DictWord,
            temperature=self.temperature,
        )

        message = response.choices[0].message

        if message.parsed is None:
            raise ValueError(
                f"OpenAI returned an invalid dictionary response for: {text}"
            )

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
