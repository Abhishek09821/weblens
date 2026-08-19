"""TLS observation analysis.

Reports the negotiated TLS protocol, cipher, and certificate validity
from one connection observation. Does not perform a full cipher audit.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "security.tls"


class SecurityTlsAnalyzer:
    """Reports TLS connection details where available."""

    id = ANALYZER_ID
    section = SectionKey.SECURITY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.TLS})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        tls = ctx.evidence.tls
        if tls is None:
            return AnalyzerOutput(findings=[])

        findings = []

        if tls.error:
            findings.append(
                self._build.detected(
                    "tls-error",
                    category="transport",
                    name="TLS connection error",
                    value=tls.error,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.TLS_CONNECTION,
                            source="tls.error",
                            excerpt=tls.error[:200],
                        )
                    ],
                )
            )
            return AnalyzerOutput(findings=findings)

        # Protocol version
        if tls.protocol:
            findings.append(
                self._build.detected(
                    "protocol",
                    category="transport",
                    name="TLS protocol version",
                    value=tls.protocol,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.TLS_CONNECTION,
                            source="tls.protocol",
                            excerpt=tls.protocol,
                        )
                    ],
                )
            )

        # Cipher
        if tls.cipher_name:
            findings.append(
                self._build.detected(
                    "cipher",
                    category="transport",
                    name="TLS cipher suite",
                    value=tls.cipher_name,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.TLS_CONNECTION,
                            source="tls.cipher_name",
                            excerpt=f"{tls.cipher_name} ({tls.cipher_bits} bits)"
                            if tls.cipher_bits
                            else tls.cipher_name,
                        )
                    ],
                )
            )

        # Certificate
        if tls.certificate:
            cert = tls.certificate
            if cert.days_until_expiry is not None:
                findings.append(
                    self._build.detected(
                        "cert-expiry",
                        category="transport",
                        name="Certificate validity",
                        value=cert.days_until_expiry,
                        unit="days",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.TLS_CONNECTION,
                                source="tls.certificate",
                                excerpt=f"Expires in {cert.days_until_expiry} days",
                            )
                        ],
                        details={
                            "issuer": cert.issuer_organization or cert.issuer_common_name,
                            "is_valid": cert.is_currently_valid,
                        },
                    )
                )

        return AnalyzerOutput(findings=findings)
