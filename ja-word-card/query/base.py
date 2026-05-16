from abc import ABC, abstractmethod

from pydantic import BaseModel


class DictExample(BaseModel):
    original_text: str
    translated_text: str


class DictExplanation(BaseModel):
    text: str
    examples: list[DictExample]


class DictWord(BaseModel):
    text: str
    pronounce: str
    explanations: list[DictExplanation]


class BaseQuery(ABC):
    name: str

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_loaded(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def query(self, text: str) -> DictWord:
        raise NotImplementedError
