"""LLM-based inference provider.

Implements the InferenceProvider protocol using an OpenAI-compatible API endpoint.
Supports OpenAI, Groq, and any provider with the same chat completions API shape.

Key constraints:
- All claims must carry structured verdicts with basis and limitations.
- Confidence must reflect evidence quality, not the model's self-assessment.
- Private/internal technology must be marked NOT_PUBLICLY_DETERMINABLE.
- The provider NEVER produces VERIFIED status — only AI_INFERRED or negative verdicts.
- Never fabricates research sources or citations.
"""

from __future__ import annotations

import json

import httpx

from weblens.ai.inference import (
    InferenceClaim,
    InferenceQuestion,
    InferenceResult,
)
from weblens.ai.verdicts import VerdictCategory, verdict_to_confidence
from weblens.domain.enums import Confidence
from weblens.domain.observations.research import ResearchObservation
from weblens.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a website reverse engineering intelligence analyst for WebLens. You analyze publicly \
observable evidence collected from websites and produce structured technology verdicts.

RULES:
1. You MUST only make claims supported by the evidence provided.
2. You MUST clearly distinguish between what is directly observable and what is inferred.
3. For private backend technologies (database, internal framework, queue, cache): \
mark them as NOT_PUBLICLY_DETERMINABLE unless public evidence explicitly confirms them.
4. Never fabricate research sources, citations, or evidence.
5. Every claim must include the specific evidence basis.
6. Confidence must reflect evidence quality:
   - 80-100%: Multiple independent strong signals
   - 60-79%: Clear signals with some uncertainty
   - 40-59%: Reasonable inference from indirect signals
   - 20-39%: Plausible but weak evidence
   - 0-19%: Speculation (should be NOT_PUBLICLY_DETERMINABLE instead)

VERDICT CATEGORIES:
- strongly_supported: Multiple independent evidence sources strongly support the claim
- likely: More likely than alternatives but uncertain
- possible: Plausible but weak evidence
- not_detected: Technology/signal was checked for and not observed
- not_publicly_determinable: Information is internal/private, cannot be publicly verified
- unable_to_verify: Insufficient evidence to evaluate

OUTPUT FORMAT:
Return a JSON array of verdict objects:
[
  {
    "claim": "Technology/architecture assertion",
    "verdict": "strongly_supported|likely|possible|...",
    "confidence": 0-100,
    "reasoning": "Chain of reasoning from evidence to conclusion",
    "basis": ["specific evidence item 1", "specific evidence item 2"],
    "limitations": ["what cannot be verified"],
    "section": "technology|design|security|traffic"
  }
]

IMPORTANT: Only output the JSON array. No markdown, no explanation outside the JSON.
"""


class LLMInferenceProvider:
    """OpenAI-compatible LLM inference provider.

    Works with OpenAI, Groq, Together AI, or any provider implementing the
    chat completions API at the configured base URL.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def name(self) -> str:
        return f"llm:{self._model}"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def infer(
        self,
        questions: list[InferenceQuestion],
        evidence_summary: dict[str, object],
        research: ResearchObservation | None,
    ) -> list[InferenceResult]:
        """Run inference on a set of questions using the LLM.

        Each question becomes a separate inference attempt. Results are returned
        even if some questions fail.
        """
        results: list[InferenceResult] = []

        for question in questions:
            result = await self._infer_question(question, evidence_summary, research)
            results.append(result)

        return results

    async def _infer_question(
        self,
        question: InferenceQuestion,
        evidence_summary: dict[str, object],
        research: ResearchObservation | None,
    ) -> InferenceResult:
        """Run inference for a single question."""
        try:
            user_prompt = self._build_user_prompt(question, evidence_summary, research)

            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()

            raw_content = data["choices"][0]["message"]["content"]
            claims = self._parse_response(raw_content, question)

            return InferenceResult(
                question_id=question.id,
                claims=claims,
                raw_response=raw_content[:500],
            )

        except httpx.HTTPStatusError as exc:
            error_msg = f"LLM API error: {exc.response.status_code}"
            logger.warning(
                "inference API error",
                extra={"question": question.id, "status": exc.response.status_code},
            )
            return InferenceResult(question_id=question.id, error=error_msg)
        except Exception as exc:
            error_msg = f"Inference failed: {str(exc)[:200]}"
            logger.warning("inference failed", extra={"question": question.id, "error": error_msg})
            return InferenceResult(question_id=question.id, error=error_msg)

    def _build_user_prompt(
        self,
        question: InferenceQuestion,
        evidence_summary: dict[str, object],
        research: ResearchObservation | None,
    ) -> str:
        """Build the user prompt with evidence context."""
        parts: list[str] = []

        parts.append(f"QUESTION: {question.question}")
        parts.append(f"\nSECTION: {question.section}")

        if question.context:
            parts.append(f"\nCONTEXT: {question.context}")

        # Add evidence summary (compact)
        parts.append("\n--- EVIDENCE ---")
        evidence_str = json.dumps(evidence_summary, default=str, indent=None)
        # Truncate if too long
        if len(evidence_str) > 3000:
            evidence_str = evidence_str[:3000] + "..."
        parts.append(evidence_str)

        # Add research results if available
        if research and research.results:
            parts.append("\n--- PUBLIC RESEARCH ---")
            for ref in research.results[:10]:
                parts.append(
                    f"- [{ref.source_type}] {ref.title} ({ref.domain}): {ref.excerpt[:150]}"
                )

        parts.append(
            "\n\nProvide your verdicts as a JSON array. "
            "Mark private/internal technologies as not_publicly_determinable."
        )

        return "\n".join(parts)

    def _parse_response(
        self,
        raw_content: str,
        question: InferenceQuestion,
    ) -> list[InferenceClaim]:
        """Parse LLM response into InferenceClaims with verdict enforcement."""
        try:
            # Try to extract JSON from the response
            parsed = json.loads(raw_content)

            # Handle both {"verdicts": [...]} and direct array
            if isinstance(parsed, dict):
                verdicts = parsed.get("verdicts", parsed.get("claims", parsed.get("results", [])))
                if not isinstance(verdicts, list):
                    verdicts = [parsed]
            elif isinstance(parsed, list):
                verdicts = parsed
            else:
                return []

            claims: list[InferenceClaim] = []
            for item in verdicts:
                if not isinstance(item, dict):
                    continue

                claim_text = item.get("claim", "")
                if not claim_text:
                    continue

                # Parse verdict category
                verdict_str = item.get("verdict", "possible")
                try:
                    verdict_cat = VerdictCategory(verdict_str)
                except ValueError:
                    verdict_cat = VerdictCategory.POSSIBLE

                # Skip VERIFIED — AI cannot produce that
                if verdict_cat == VerdictCategory.VERIFIED:
                    verdict_cat = VerdictCategory.STRONGLY_SUPPORTED

                # Parse confidence and enforce evidence-quality caps
                raw_confidence = int(item.get("confidence", 50))
                basis = item.get("basis", [])
                if not isinstance(basis, list):
                    basis = []

                # Cap confidence based on evidence
                from weblens.ai.verdicts import Verdict
                from weblens.ai.verdicts import cap_confidence as _cap

                temp_verdict = Verdict(
                    claim=claim_text,
                    category=verdict_cat,
                    confidence=raw_confidence,
                    basis=basis,
                    limitations=item.get("limitations", []),
                    section=item.get("section", question.section),
                )
                capped = _cap(temp_verdict)

                # Map verdict to internal confidence
                confidence = verdict_to_confidence(verdict_cat, capped.confidence)

                # Skip claims that are too weak or about unknowable things
                # (they become NOT_DETERMINABLE findings instead)
                if verdict_cat in (
                    VerdictCategory.NOT_PUBLICLY_DETERMINABLE,
                    VerdictCategory.UNABLE_TO_VERIFY,
                    VerdictCategory.NOT_DETECTED,
                ):
                    # These become negative findings via a different code path
                    confidence = Confidence.MODERATE

                claims.append(
                    InferenceClaim(
                        claim=claim_text,
                        confidence=confidence,
                        reasoning=item.get("reasoning", ""),
                        basis=basis[:5],
                        limitations=item.get("limitations", []),
                    )
                )

            return claims

        except json.JSONDecodeError:
            logger.warning("failed to parse LLM JSON response", extra={"raw": raw_content[:200]})
            return []
        except Exception as exc:
            logger.warning("failed to parse inference response", extra={"error": str(exc)[:200]})
            return []


def get_llm_inference_provider(
    api_key: str,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
) -> LLMInferenceProvider:
    """Create an LLM inference provider instance."""
    return LLMInferenceProvider(api_key=api_key, model=model, base_url=base_url)
