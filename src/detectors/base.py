"""
Base interfaces and data models for PII detection engines.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EntitySpan(BaseModel):
    """Represents a detected PII span in normalized text coordinates."""
    entity_id: str = Field(description="Unique identifier for span")
    type: str = Field(description="Entity type: PERSON, EMAIL, PHONE, ORGANIZATION, ADDRESS, SSN_TAX_ID, CREDIT_CARD, DATE_OF_BIRTH, IP_ADDRESS")
    text: str = Field(description="Raw text snippet of entity")
    start: int = Field(description="Start character index (inclusive)")
    end: int = Field(description="End character index (exclusive)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")
    detector_sources: List[str] = Field(default_factory=list, description="List of detector IDs that flagged this span")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary detector metadata")

    def overlaps_with(self, other: "EntitySpan") -> bool:
        """Checks if this span overlaps with another span."""
        return max(self.start, other.start) < min(self.end, other.end)

    def contains(self, other: "EntitySpan") -> bool:
        """Checks if this span completely encloses another span."""
        return self.start <= other.start and self.end >= other.end


class BaseDetector(ABC):
    """Abstract interface for all PII detectors."""

    @property
    @abstractmethod
    def detector_id(self) -> str:
        """Unique identifier for this detector."""
        pass

    @abstractmethod
    def detect(self, text: str, block_context: Optional[Dict[str, Any]] = None) -> List[EntitySpan]:
        """
        Analyzes the given normalized text and returns detected PII candidate spans.
        """
        pass
