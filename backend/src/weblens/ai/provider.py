"""AI provider protocol and the default null implementation.

Two guarantees this module exists to keep:

1. **AI is never on the detection path.** A provider receives a finished
   :class:`AnalysisResult` and returns prose. It cannot add, alter, or veto a finding.
2. **Ungrounded statements do not ship.** Every sentence a provider produces must cite finding
   ids that exist in the result. :mod:`weblens.ai.grounding` drops the rest and reports them as
   ``dropped_claims`` rather than hiding the fact that something was removed.

The default provider is ``NullProvider``: with no configuration, the endpoint returns 501 and
nothing about a scan changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from weblens.config import Settings
from weblens.domain.enums import SectionKey
from weblens.domain.errors import AiDisabledError
from weblens.domain.scan import AnalysisResult

if TYPE_CHECKING:  # avoids a runtime import cycle with the route module
    from weblens.api.routes.ai import ExplainResponse


class AiProvider(Protocol):
    name: str

    async def explain(
        self,
        result: AnalysisResult,
        sections: list[SectionKey] | None,
        audience: str,
    ) -> ExplainResponse: ...


class NullProvider:
    """The configured default. Declines instead of inventing."""

    name = "none"

    async def explain(
        self,
        result: AnalysisResult,
        sections: list[SectionKey] | None,
        audience: str,
    ) -> ExplainResponse:
        del result, sections, audience
        raise AiDisabledError(
            "No AI provider is configured. WebLens produces its analysis without one; the "
            "explanation layer is optional and adds no detection capability."
        )


def get_provider(settings: Settings) -> AiProvider:
    if settings.ai_provider == "none":
        return NullProvider()
    # Unreachable while the settings field only accepts "none"; kept so adding a provider is a
    # single registration rather than a refactor.
    raise AiDisabledError(f"AI provider '{settings.ai_provider}' is not available in this build.")
