from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Platform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    REELS = "reels"
    SHORTS = "shorts"


class PlanStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EffectType(str, Enum):
    HEADLINE = "headline"
    CTA = "cta"
    SUBTITLE_STYLE = "subtitle_style"
    ZOOM_IN = "zoom_in"
    B_ROLL = "b_roll"


class ViralScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hook: int = Field(ge=0, le=10)
    curiosity: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    emotion: int = Field(ge=0, le=10)
    originality: int = Field(ge=0, le=10)
    sharing: int = Field(ge=0, le=10)
    comments: int = Field(ge=0, le=10)
    retention: int = Field(ge=0, le=10)
    payoff: int = Field(ge=0, le=10)
    total: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def total_must_match_components(self) -> "ViralScore":
        calculated = sum(
            (
                self.hook,
                self.curiosity,
                self.clarity,
                self.relevance,
                self.emotion,
                self.originality,
                self.sharing,
                self.comments,
                self.retention,
                self.payoff,
            )
        )
        if self.total != calculated:
            raise ValueError(
                f"viral_score.total={self.total}, mas a soma dos critérios é {calculated}"
            )
        return self


class CutSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    reason: str = Field(min_length=1)
    keep: bool = True
    text: Optional[str] = None
    viral_score: Optional[ViralScore] = None

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "CutSegment":
        if self.end_time <= self.start_time:
            raise ValueError("end_time precisa ser maior que start_time")
        return self


class VisualEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effect_type: EffectType
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "VisualEffect":
        if self.end_time <= self.start_time:
            raise ValueError("end_time do efeito precisa ser maior que start_time")
        return self


class SeoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    platform: Platform


class EditPlan(BaseModel):
    """Contrato auditável entre o agente que decide e o motor que renderiza."""

    model_config = ConfigDict(extra="forbid")

    video_source: str
    target_duration: float = Field(gt=0)
    segments: List[CutSegment] = Field(default_factory=list)
    effects: List[VisualEffect] = Field(default_factory=list)
    seo: List[SeoMetadata] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING_APPROVAL

    # Compatibilidade explícita com o primeiro plano criado pelo protótipo.
    platform: Optional[Platform] = Field(default=None, exclude=True)
    seo_metadata: Optional[SeoMetadata] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "EditPlan":
        if not self.segments:
            raise ValueError("o plano precisa conter ao menos um segmento")

        selected_duration = sum(
            segment.end_time - segment.start_time
            for segment in self.segments
            if segment.keep
        )
        if selected_duration <= 0:
            raise ValueError("o plano não possui segmentos selecionados")

        if self.seo_metadata and not self.seo:
            self.seo = [self.seo_metadata]

        if self.platform and not self.seo:
            self.seo = [SeoMetadata(platform=self.platform)]

        if self.platform and self.seo:
            if any(item.platform != self.platform for item in self.seo):
                raise ValueError("platform e seo[].platform entram em conflito")

        return self

    @property
    def selected_duration(self) -> float:
        return sum(
            segment.end_time - segment.start_time
            for segment in self.segments
            if segment.keep
        )

    @property
    def target_platform(self) -> Platform:
        if self.seo:
            return self.seo[0].platform
        if self.platform:
            return self.platform
        return Platform.YOUTUBE

    def export_json(self, path: str) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            self.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

    @classmethod
    def load_json(cls, path: str) -> "EditPlan":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
