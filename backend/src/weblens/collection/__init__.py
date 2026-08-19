"""Collection layer: the only code permitted to touch the network.

Everything here produces :class:`~weblens.domain.evidence.RawEvidence`. Nothing here
interprets it - that is the analyzers' job, and the separation is what keeps analyzers pure
and testable offline.
"""
