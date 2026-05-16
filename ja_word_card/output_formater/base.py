from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from ..query import DictWord


class BaseFormatter(ABC):
    name: str

    @abstractmethod
    def format(self, word: DictWord) -> str:
        raise NotImplementedError

    @abstractmethod
    def format_many(self, words: Mapping[str, DictWord]) -> str:
        raise NotImplementedError
