from __future__ import annotations

from collections.abc import Mapping
from html import escape

from ..query import DictExplanation, DictWord

from .base import BaseFormatter


class AnkiFormatter(BaseFormatter):
    name = "anki"

    def format(self, word: DictWord) -> str:
        return "\t".join(
            (
                self._cell(word.text),
                self._cell(word.pronounce),
                self._format_explanations(word),
                self._format_examples(word),
            )
        )

    def format_many(self, words: Mapping[str, DictWord]) -> str:
        return "\n".join(self.format(word) for word in words.values())

    def _format_explanations(self, word: DictWord) -> str:
        items = "".join(
            f"<li>{escape(explanation.text)}</li>"
            for explanation in word.explanations
        )
        return f"<ol>{items}</ol>"

    def _format_examples(self, word: DictWord) -> str:
        return "".join(
            self._format_example_group(explanation)
            for explanation in word.explanations
        )

    def _format_example_group(self, explanation: DictExplanation) -> str:
        items = "".join(
            "<li>"
            f"{escape(example.original_text)}"
            "<br>"
            f"{escape(example.translated_text)}"
            "</li>"
            for example in explanation.examples
        )
        return f"<small>{escape(explanation.text)}</small><ul>{items}</ul>"

    def _cell(self, value: str) -> str:
        return escape(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
