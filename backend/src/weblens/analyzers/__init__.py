"""Deterministic analyzers.

Pure functions from :class:`~weblens.domain.evidence.RawEvidence` to findings. No module in
this package may import ``weblens.collection``, ``httpx``, ``socket``, or ``playwright`` - the
absence of I/O is what makes analyzers reproducible and what guarantees a scan contacts the
target exactly once.
"""
