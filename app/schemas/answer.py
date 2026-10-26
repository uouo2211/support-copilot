from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[str] = Field(max_length=8)
    applicability: str = Field(max_length=1000)
    missing_context: list[str] = Field(max_length=10)
    decision: Literal["suggest", "clarify", "handoff", "deny"]
    reason_codes: list[str] = Field(max_length=10)


class Citation(BaseModel):
    evidence_id: str
    revision_id: str
    source_id: str
    title: str
    excerpt: str
    external_allowed: bool


class Answer(BaseModel):
    answer: str
    citations: list[Citation]
    applicability: str
    missing_context: list[str]
    decision: Literal["suggest", "clarify", "handoff", "deny"]
    reason_codes: list[str]
    retrieval: str = "BM25"
