from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

class BaseExtractor(ABC):
    name: str

    @abstractmethod
    def detect(self, lower_text: str) -> bool: ...

    @abstractmethod
    def parse(self, session: Session, path: str): ...

    @abstractmethod
    def summary(self, path: str) -> dict: ...
