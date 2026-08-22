"""AI summary generation using Groq (free tier, Llama models).

The AI layer ONLY summarizes existing verified findings.
It cannot detect technologies, invent claims, or modify factual values.
Every AI-generated statement must be traceable to findings passed as input.

The application works completely without AI — this is an optional enhancement.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from weblens.logging import get_logger

logger = get_logger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3.6-27b"

SYSTEM_PROMPT = """You are a technical writer summarizing website analysis findings for WebLens.

RULES:
1. Only summarize information provided in the structured findings below.
2. NEVER invent technologies, claims, or values not present in the data.
3. NEVER modify numerical values, scores, or measurements.
4. If something is marked "inferred", say "likely" or "appears to".
5. If something is "not detected", say so honestly — don't guess.
6. Write clearly and concisely for a technical audience.
7. Organize information logically.
8. Include the specific values (colors, fonts, metrics) from the data.
9. The summary should help someone understand the website's technical makeup
   well enough to discuss it knowledgeably or recreate similar aspects.

Format your response as a clear, structured summary with sections.
Use markdown formatting. Keep it under 800 words."""


def get_groq_key() -> str | None:
    """Get Groq API key from environment or .env file. Returns None if not configured."""
    # Check os.environ first
    key = os.environ.get("GROQ_API_KEY") or os.environ.get("WEBLENS_GROQ_API_KEY")
    if key:
        return key
    # Fall back to reading .env file directly
    try:
        from pathlib import Path

        env_paths = [Path(".env"), Path("../.env"), Path(__file__).resolve().parents[3] / ".env"]
        for env_path in env_paths:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val and not val.startswith("gsk_your_"):
                            return val
    except Exception:  # noqa: S110 - intentional: .env discovery is best-effort
        pass
    return None


def is_ai_available() -> bool:
    """Check if AI summarization is available."""
    return get_groq_key() is not None


async def generate_summary(findings_data: dict[str, Any]) -> str | None:
    """Generate an AI summary from structured findings.

    Returns None if AI is unavailable or fails. The application
    must work without this — it's purely additive.
    """
    api_key = get_groq_key()
    if not api_key:
        return None

    # Build a concise representation of findings for the AI
    prompt = _build_prompt(findings_data)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
            )
            if response.status_code != 200:
                logger.warning("Groq API returned %d", response.status_code)
                return None

            data = response.json()
            content: str = data["choices"][0]["message"]["content"]
            # Strip thinking blocks from models that expose chain-of-thought
            if "<think>" in content:
                parts = content.split("</think>")
                content = parts[-1].strip() if len(parts) > 1 else content
            return content

    except Exception as exc:
        logger.warning("AI summary generation failed: %s", str(exc)[:200])
        return None


def _build_prompt(data: dict[str, Any]) -> str:
    """Build a prompt from structured analysis data."""
    parts = ["Summarize this website analysis for the target:\n"]

    target = data.get("target", {})
    parts.append(f"Website: {target.get('host', 'unknown')}")
    parts.append(f"URL: {target.get('final_url', target.get('normalized_url', ''))}")
    parts.append("")

    # Technology
    tech = data.get("technology", [])
    if tech:
        parts.append("DETECTED TECHNOLOGIES:")
        for item in tech:
            status = item.get("status", "")
            parts.append(f"  - {item.get('name')}: {status}")
        parts.append("")

    # Security
    security = data.get("security", {})
    if security.get("percentage") is not None:
        pct = security["percentage"]
        band = security.get("band_phrase", "")
        parts.append(f"SECURITY POSTURE: {pct}% ({band})")
        for rule in security.get("strong_controls", []):
            parts.append(f"  ✓ {rule}")
        for rule in security.get("missing_controls", []):
            parts.append(f"  ✗ {rule}")
        parts.append("")

    # Design
    design = data.get("design", {})
    if design:
        parts.append("DESIGN:")
        if design.get("fonts"):
            parts.append(f"  Fonts: {', '.join(design['fonts'])}")
        if design.get("colors"):
            parts.append(f"  Colors: {', '.join(design['colors'][:6])}")
        if design.get("layout"):
            parts.append(f"  Layout: {', '.join(design['layout'][:5])}")
        parts.append("")

    # Performance
    perf = data.get("performance", {})
    if perf:
        parts.append("PERFORMANCE:")
        for key, val in perf.items():
            if val is not None:
                parts.append(f"  {key}: {val}")
        parts.append("")

    # Architecture
    arch = data.get("architecture", {})
    if arch:
        parts.append("ARCHITECTURE:")
        if arch.get("rendering"):
            parts.append(f"  Rendering: {arch['rendering']}")
        if arch.get("infrastructure"):
            parts.append(f"  Infrastructure: {', '.join(arch['infrastructure'])}")
        parts.append("")

    # Traffic
    traffic = data.get("traffic", [])
    if traffic:
        parts.append("TRAFFIC/ANALYTICS:")
        for item in traffic[:10]:
            parts.append(f"  - {item.get('name')}: {item.get('status')}")
        parts.append("")

    return "\n".join(parts)


def build_summary_input(result_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract a summary-friendly representation from an AnalysisResult dict.

    This is what gets sent to the AI — only verified/inferred findings,
    never raw evidence or internal implementation details.

    V2: All findings live under 4 sections (design, technology, security, traffic).
    """
    sections = result_dict.get("sections", {})
    target = result_dict.get("target", {})

    # Technology (now includes architecture, network, performance, SEO findings)
    tech_findings = sections.get("technology", {}).get("findings", [])
    tech_items = [
        {"name": f["name"], "status": f["status"], "value": f.get("value")}
        for f in tech_findings
        if f["status"] in ("verified", "strongly_inferred", "inferred")
    ]

    # Security
    sec_data = sections.get("security", {}).get("data", {})
    score = sec_data.get("score", {}) if sec_data else {}
    security = {}
    if score and score.get("percentage") is not None:
        security = {
            "percentage": score["percentage"],
            "band_phrase": score.get("band_phrase"),
            "strong_controls": [
                r["title"] for r in score.get("rules", []) if r["outcome"] == "pass"
            ],
            "missing_controls": [
                r["title"] for r in score.get("rules", []) if r["outcome"] == "fail"
            ],
        }

    # Design
    design_findings = sections.get("design", {}).get("findings", [])
    design = {}
    for f in design_findings:
        if f["id"] == "design.typography:loaded-fonts" and f.get("values"):
            design["fonts"] = f["values"][:6]
        if f["id"] == "design.color:background-colors" and f.get("values"):
            design["colors"] = f["values"][:6]
        if f["id"] == "design.layout:display-types" and f.get("values"):
            design["layout"] = f["values"][:5]

    # Extract architecture/performance from technology findings (for summary context)
    arch: dict[str, Any] = {}
    perf: dict[str, Any] = {}
    for f in tech_findings:
        if f["id"] == "architecture.rendering:rendering-strategy" and f.get("value"):
            arch["rendering"] = str(f["value"])
        if f["source"] == "architecture.platform" and f.get("detected"):
            arch.setdefault("infrastructure", []).append(str(f.get("value", f["name"])))
        if (
            f["source"] in ("performance.timings", "performance.resources")
            and f["status"] == "verified"
            and f.get("value") is not None
        ):
            perf[f["name"]] = f"{f['value']} {f.get('unit', '')}".strip()

    # Traffic
    traffic_findings = sections.get("traffic", {}).get("findings", [])
    traffic = [
        {"name": f["name"], "status": f["status"], "value": f.get("value")}
        for f in traffic_findings
        if f["status"] in ("verified", "strongly_inferred", "inferred")
    ]

    return {
        "target": target,
        "technology": tech_items,
        "security": security,
        "design": design,
        "performance": perf,
        "architecture": arch,
        "traffic": traffic,
    }
