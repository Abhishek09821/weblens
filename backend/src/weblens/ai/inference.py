"""AI inference layer.

Runs AFTER deterministic analysis and (optionally) public research. Produces structured
findings with ``status=AI_INFERRED`` that carry explicit reasoning, confidence, and source
references. These findings are kept structurally separate from deterministic detection.

Key constraints:
- AI inference CANNOT produce ``status=VERIFIED`` findings.
- AI inference CANNOT modify or remove existing deterministic findings.
- Every AI-inferred finding must carry at least one EvidenceRef documenting the basis.
- If evidence is insufficient, AI must return NOT_DETERMINABLE rather than guess.
- If no AI provider is configured, the inference phase is skipped cleanly.
- The application works identically without AI — this is additive.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.enums import Confidence, EvidenceKind, FindingStatus
from weblens.domain.evidence import EvidenceRef
from weblens.domain.findings import Finding
from weblens.domain.observations.research import ResearchObservation
from weblens.logging import get_logger

logger = get_logger(__name__)


class InferenceQuestion(BaseModel):
    """A structured question for the AI inference engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Unique identifier for this question, e.g. 'backend_technology'.")
    question: str = Field(description="The question to answer based on evidence.")
    context: str = Field(default="", description="Additional context to provide to the model.")
    section: str = Field(description="Which report section this question feeds into.")


class InferenceClaim(BaseModel):
    """One structured AI inference claim — the raw output before conversion to Finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str = Field(description="The technology/architecture assertion.")
    confidence: Confidence = Field(description="How confident the AI is.")
    reasoning: str = Field(description="Chain of reasoning that led to this claim.")
    basis: list[str] = Field(
        default_factory=list,
        description="Finding IDs or research URLs that support this claim.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="What cannot be determined or verified about this claim.",
    )


class InferenceResult(BaseModel):
    """Complete output of an inference run."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    claims: list[InferenceClaim] = Field(default_factory=list)
    raw_response: str | None = Field(
        default=None, description="The raw LLM response for debugging."
    )
    error: str | None = Field(default=None, description="Error message if inference failed.")


@runtime_checkable
class InferenceProvider(Protocol):
    """Adapter interface for AI inference.

    Implementations must:
    - Accept structured evidence and research, not raw page content.
    - Return structured claims with confidence and reasoning.
    - Never produce VERIFIED status — only AI_INFERRED or NOT_DETERMINABLE.
    - Never silently invent technology without basis.
    - Return empty results on failure rather than raising.
    """

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    def is_available(self) -> bool:
        """Whether this provider can actually run inference."""
        ...

    async def infer(
        self,
        questions: list[InferenceQuestion],
        evidence_summary: dict[str, object],
        research: ResearchObservation | None,
    ) -> list[InferenceResult]:
        """Run inference on a set of questions.

        Returns results for each question. Empty claims list means the AI could not
        determine an answer (which is the correct behavior for insufficient evidence).
        """
        ...


class NullInferenceProvider:
    """Default when no AI is configured. Returns empty results for all questions."""

    @property
    def name(self) -> str:
        return "none"

    @property
    def is_available(self) -> bool:
        return False

    async def infer(
        self,
        questions: list[InferenceQuestion],
        evidence_summary: dict[str, object],
        research: ResearchObservation | None,
    ) -> list[InferenceResult]:
        return []


def claims_to_findings(
    results: list[InferenceResult],
    source: str = "ai.inference",
) -> list[Finding]:
    """Convert AI inference results into Finding objects with proper provenance.

    Only claims with at least moderate confidence become findings.
    All produced findings carry status=AI_INFERRED and an EvidenceRef documenting
    the reasoning.
    """
    findings: list[Finding] = []

    for result in results:
        if result.error:
            logger.warning(
                "inference question failed",
                extra={"question": result.question_id, "error": result.error[:200]},
            )
            continue

        for claim in result.claims:
            if claim.confidence == Confidence.WEAK:
                # Weak confidence does not meet the bar for inclusion.
                continue

            evidence_ref = EvidenceRef(
                kind=EvidenceKind.AI_REASONING,
                source=source,
                excerpt=claim.reasoning[:300] if claim.reasoning else None,
                detail={
                    "confidence": claim.confidence.value,
                    "basis": ", ".join(claim.basis[:5]),
                },
            )

            finding = Finding(
                id=f"{source}:{result.question_id}:{_slugify(claim.claim)}",
                category="ai_inference",
                name=claim.claim,
                status=FindingStatus.AI_INFERRED,
                confidence=claim.confidence,
                evidence=[evidence_ref],
                source=source,
                limitations=claim.limitations,
            )
            findings.append(finding)

    return findings


def get_inference_provider(provider_name: str | None = None) -> InferenceProvider:
    """Resolve an inference provider by name.

    Returns NullInferenceProvider when no provider is configured.
    Supported providers: 'none', 'openai', 'groq'.
    """
    if not provider_name or provider_name == "none":
        return NullInferenceProvider()

    if provider_name in ("openai", "groq", "together", "llm"):
        from weblens.config import get_settings

        settings = get_settings()
        api_key = settings.inference_api_key
        if not api_key:
            logger.warning(
                f"{provider_name} inference provider requested but "
                "WEBLENS_INFERENCE_API_KEY is not set"
            )
            return NullInferenceProvider()

        model = settings.inference_model
        # Default models per provider
        if not model:
            defaults = {
                "openai": "gpt-4o-mini",
                "groq": "llama-3.1-70b-versatile",
                "together": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                "llm": "gpt-4o-mini",
            }
            model = defaults.get(provider_name, "gpt-4o-mini")

        # Base URLs per provider
        base_urls = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "together": "https://api.together.xyz/v1",
            "llm": "https://api.openai.com/v1",
        }
        base_url = base_urls.get(provider_name, "https://api.openai.com/v1")

        from weblens.ai.llm_inference import get_llm_inference_provider

        return get_llm_inference_provider(api_key=api_key, model=model, base_url=base_url)

    logger.warning(
        "unknown inference provider requested, falling back to none",
        extra={"provider": provider_name},
    )
    return NullInferenceProvider()


def _slugify(text: str) -> str:
    """Create a short slug from a claim text for finding IDs."""
    return text.lower().replace(" ", "-").replace("/", "-").replace(".", "-")[:40].rstrip("-")
