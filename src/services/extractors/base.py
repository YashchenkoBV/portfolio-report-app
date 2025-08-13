"""Abstract base class for PDF extractors.

Each extractor must implement ``detect`` and ``parse``. ``detect`` should
examine the lower‑cased text of the PDF (usually just the first few pages)
and return True if the extractor can parse the file. ``parse`` takes a
database session and a path to the PDF and performs the extraction,
persisting results to the database.

Extractors may also implement ``summary`` which returns a dictionary of
headline numbers for display without writing to the database. The default
implementation returns an empty dict.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class BaseExtractor(ABC):
    name: str

    @abstractmethod
    def detect(self, lower_text: str) -> bool:
        """Return True if this extractor can handle the given text."""
        ...

    @abstractmethod
    def parse(self, session: Session, path: str):
        """Parse the given PDF into the database."""
        ...

    def summary(self, path: str) -> dict:
        """Return headline numbers from the PDF.

        This optional method can be overridden by subclasses. The default
        implementation returns an empty dictionary.
        """
        return {}