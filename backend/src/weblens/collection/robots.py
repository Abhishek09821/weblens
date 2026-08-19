"""robots.txt fetching and evaluation.

WebLens identifies itself and honours disallow rules by default. This is a small,
deliberately conservative implementation of the matching rules from RFC 9309: longest match
wins, ``Allow`` wins ties, and ``*``/``$`` wildcards are supported.

When robots.txt cannot be fetched or parsed, the verdict is ``None`` (unknown) rather than
``True``. "We could not check" and "we checked and it is permitted" are different claims.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WEBLENS_AGENT_TOKEN = "weblens"  # noqa: S105 - a user-agent token, not a secret
_WILDCARD_AGENT = "*"


@dataclass
class _Rule:
    allow: bool
    pattern: str
    matcher: re.Pattern[str]

    @property
    def specificity(self) -> int:
        return len(self.pattern)


@dataclass
class RobotsPolicy:
    rules_by_agent: dict[str, list[_Rule]] = field(default_factory=dict)
    sitemaps: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, text: str) -> RobotsPolicy:
        policy = cls()
        current_agents: list[str] = []
        starting_new_group = True

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field_name, _, value = line.partition(":")
            key = field_name.strip().lower()
            value = value.strip()

            if key == "user-agent":
                if not starting_new_group:
                    current_agents = []
                    starting_new_group = True
                current_agents.append(value.lower())
                policy.rules_by_agent.setdefault(value.lower(), [])
            elif key in ("allow", "disallow"):
                starting_new_group = False
                if not current_agents:
                    continue
                if key == "disallow" and value == "":
                    # An empty Disallow permits everything; it carries no restriction.
                    continue
                rule = _Rule(allow=key == "allow", pattern=value, matcher=_compile(value))
                for agent in current_agents:
                    policy.rules_by_agent.setdefault(agent, []).append(rule)
            elif key == "sitemap" and value:
                policy.sitemaps.append(value)

        return policy

    def group_for(self, agent_token: str = WEBLENS_AGENT_TOKEN) -> tuple[str | None, list[_Rule]]:
        """Most specific matching group: our token first, then ``*``."""
        token = agent_token.lower()
        for agent, rules in self.rules_by_agent.items():
            if agent and agent != _WILDCARD_AGENT and agent in token:
                return agent, rules
        if _WILDCARD_AGENT in self.rules_by_agent:
            return _WILDCARD_AGENT, self.rules_by_agent[_WILDCARD_AGENT]
        return None, []

    def evaluate(
        self, path: str, agent_token: str = WEBLENS_AGENT_TOKEN
    ) -> tuple[bool, str | None, str | None]:
        """Return ``(allowed, matched_directive, user_agent_group)``."""
        agent, rules = self.group_for(agent_token)
        if not rules:
            return True, None, agent

        best: _Rule | None = None
        for rule in rules:
            if not rule.matcher.match(path):
                continue
            if best is None or rule.specificity > best.specificity:
                best = rule
            elif rule.specificity == best.specificity and rule.allow:
                best = rule  # Allow wins ties.

        if best is None:
            return True, None, agent
        directive = f"{'Allow' if best.allow else 'Disallow'}: {best.pattern}"
        return best.allow, directive, agent


def _compile(pattern: str) -> re.Pattern[str]:
    """Translate a robots path pattern into an anchored regular expression."""
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    parts = [re.escape(segment) for segment in body.split("*")]
    expression = ".*".join(parts)
    if anchored_end:
        expression += "$"
    return re.compile(expression or ".*")
