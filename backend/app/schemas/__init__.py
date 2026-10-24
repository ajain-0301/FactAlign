from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Language = Literal["auto", "hi", "en", "hinglish"]
OutputLanguage = Literal["same", "hi", "en", "hinglish"]
Strategy = Literal["standard", "factuality"]
Length = Literal["short", "medium", "long"]
VerifyMethod = Literal["auto", "rule", "llm", "hybrid", "claim_nli"]


def _clean_text(v: str, field: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError(f"{field} must not be empty")
    return v


class SourcePage(BaseModel):
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class PageReferencedRequest(BaseModel):
    @model_validator(mode="after")
    def validate_pages(self):
        source = getattr(self, "source", None) or getattr(self, "text", "")
        pages = getattr(self, "source_pages", None)
        if pages is None:
            return self
        cursor = 0
        previous_page = 0
        for page in pages:
            if page.start < cursor or page.end <= page.start or page.end > len(source) or source[cursor:page.start].strip() or page.page <= previous_page:
                raise ValueError("Page references must cover the source in increasing page and offset order")
            cursor, previous_page = page.end, page.page
        if source[cursor:].strip():
            raise ValueError("Page references must cover the entire source")
        return self


class SummarizeRequest(PageReferencedRequest):
    text: str
    source_pages: list[SourcePage] | None = Field(default=None, max_length=10000)
    title: str | None = Field(default=None, max_length=300)
    language: Language = "auto"
    output_language: OutputLanguage = "same"
    length: Length = "medium"
    strategy: Strategy = "factuality"
    reference_summary: str | None = None
    save: bool | None = None  # None -> use the "auto-save" preference

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = _clean_text(v, "text")
        if len(v.split()) < 3:
            raise ValueError("text is too short to summarize (need at least 3 words)")
        return v


class CompareRequest(SummarizeRequest):
    strategy: Strategy = "factuality"  # ignored; both strategies are run


class VerifyRequest(PageReferencedRequest):
    source: str
    summary: str
    method: VerifyMethod = "auto"
    source_pages: list[SourcePage] | None = Field(default=None, max_length=10000)
    run_id: int | None = None

    @field_validator("source")
    @classmethod
    def _s(cls, v: str) -> str:
        return _clean_text(v, "source")

    @field_validator("summary")
    @classmethod
    def _m(cls, v: str) -> str:
        return _clean_text(v, "summary")


class ExperimentDoc(BaseModel):
    title: str | None = None
    text: str
    language: Language = "auto"
    reference_summary: str | None = None

    @field_validator("text")
    @classmethod
    def _t(cls, v: str) -> str:
        return _clean_text(v, "text")


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    language: Literal["all", "hi", "en", "hinglish"] = "all"
    strategies: list[Strategy] = Field(default_factory=lambda: ["standard", "factuality"], min_length=1)
    length: Length = "medium"
    model: str | None = None
    dataset: Literal["sample", "custom"] = "sample"
    documents: list[ExperimentDoc] = Field(default_factory=list, max_length=20)
    verify: bool = True

    @field_validator("name")
    @classmethod
    def _n(cls, v: str) -> str:
        return _clean_text(v, "name")


class EvaluationRunRequest(BaseModel):
    strategies: list[Strategy] = Field(default_factory=lambda: ["standard", "factuality"], min_length=1)
    length: Length = "short"
    language: Literal["all", "hi", "en", "hinglish"] = "all"
    verify_method: VerifyMethod = "auto"


class SettingsUpdate(BaseModel):
    provider_mode: Literal["auto", "demo", "real"] | None = None
    model: str | None = Field(default=None, max_length=100)
    default_strategy: Strategy | None = None
    default_length: Length | None = None
    default_language: Language | None = None
    default_output_language: OutputLanguage | None = None
    auto_save: bool | None = None
    verifier: VerifyMethod | None = None
