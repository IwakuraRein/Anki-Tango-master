from __future__ import annotations

import json
from collections.abc import Mapping

try:
    from query import DictWord
except ImportError:
    from ..query import DictWord

from .base import BaseFormatter


class JsonFormatter(BaseFormatter):
    name = "json"

    def format(self, word: DictWord) -> str:
        return json.dumps(self._word_to_dict(word), ensure_ascii=False, indent=2)

    def format_many(self, words: Mapping[str, DictWord]) -> str:
        return json.dumps(
            {
                query_text: self._word_to_dict(word)
                for query_text, word in words.items()
            },
            ensure_ascii=False,
            indent=2,
        )

    def _word_to_dict(self, word: DictWord) -> dict[str, object]:
        if hasattr(word, "model_dump"):
            return word.model_dump()
        return word.dict()
