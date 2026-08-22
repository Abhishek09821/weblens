"""Optional AI layer.

Three distinct roles:
1. **Inference** (pipeline phase): produces structured AI_INFERRED findings from evidence
   and research. Runs during the scan. Never produces VERIFIED findings.
2. **Verdict engine**: structures every AI conclusion with category, confidence, basis,
   sources, and limitations. Ensures AI never claims certainty without evidence.
3. **Explanation** (post-analysis): generates prose summaries of existing findings.
   Never on the detection path. Disabled by default.
"""
