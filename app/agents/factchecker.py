"""Fact-Checker agent - verifies claims against sources."""

import hashlib

import structlog

from app.data.models import Claim, EvidencePointer, Verdict, VerdictType
from app.llm.json_guard import ask_llm_json
from app.llm.prompts import FACTCHECKER_SYSTEM_PROMPT
from app.tools.retrieval import retrieve_for_query

logger = structlog.get_logger()


async def verify_claim(claim: Claim, claim_index: int) -> Verdict:
    """
    Verify a single claim against indexed sources.

    Args:
        claim: Claim to verify
        claim_index: Claim number (for logging)

    Returns:
        Verdict with evidence and confidence
    """
    logger.info("factcheck_claim_started", claim_id=claim.claim_id, index=claim_index)

    # Retrieve relevant evidence
    retrieved = await retrieve_for_query(claim.text, n_results=5)

    # Build evidence context
    evidence_context = []
    for i, result in enumerate(retrieved, 1):
        evidence_context.append(
            f"[Evidence {i}]\n"
            f"Source: {result.metadata.get('title', 'Unknown')}\n"
            f"URL: {result.metadata.get('url', 'N/A')}\n"
            f"Content: {result.text}\n"
            f"Relevance score: {result.score:.2f}\n"
        )

    context_str = "\n---\n".join(evidence_context)

    # Build prompt
    user_prompt = f"""
Verify this claim against the available evidence:

CLAIM: {claim.text}

EVIDENCE FROM SOURCES:
{context_str}

Assess whether the claim is:
- SUPPORTED: Clear evidence supports the claim (confidence >= 0.7)
- REFUTED: Evidence contradicts the claim
- NEEDS_MORE_EVIDENCE: Insufficient or conflicting evidence
- COMMON_KNOWLEDGE: Widely known fact that doesn't need citation

For SUPPORTED claims:
- Cite specific quotes from evidence
- Assign high confidence (0.7-1.0) if evidence is clear
- List all supporting evidence pointers

For REFUTED claims:
- Explain the contradiction
- Cite conflicting evidence

For NEEDS_MORE_EVIDENCE:
- Explain what's missing or unclear
- Suggest what additional sources would help

Return JSON matching the Verdict schema.
""".strip()

    messages = [
        {"role": "system", "content": FACTCHECKER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Define a temporary Pydantic model for the LLM response
    from pydantic import BaseModel, Field

    class VerdictResponse(BaseModel):
        verdict: VerdictType
        confidence: float = Field(..., ge=0.0, le=1.0)
        evidence: list[dict] = Field(default_factory=list)
        reasoning: str

    # Get verdict
    response = await ask_llm_json(
        messages=messages,
        response_model=VerdictResponse,
        task="orch",
    )

    # Convert evidence dicts to EvidencePointer objects
    evidence_pointers = []
    for ev in response.evidence:
        # Find matching retrieval result
        matching_result = None
        for result in retrieved:
            if ev.get("quote", "").lower() in result.text.lower():
                matching_result = result
                break

        if matching_result:
            pointer = EvidencePointer(
                source_id=matching_result.source_id,
                quote=ev.get("quote", ""),
                chunk_id=matching_result.chunk_id,
                relevance=ev.get("relevance", 1.0),
            )
            evidence_pointers.append(pointer)

    # Create Verdict object
    verdict = Verdict(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        verdict=response.verdict,
        confidence=response.confidence,
        evidence=evidence_pointers,
        reasoning=response.reasoning,
    )

    logger.info(
        "factcheck_claim_complete",
        claim_id=claim.claim_id,
        verdict=verdict.verdict,
        confidence=f"{verdict.confidence:.2f}",
        num_evidence=len(verdict.evidence),
    )

    return verdict


async def verify_claims(claims: list[Claim]) -> list[Verdict]:
    """
    Verify multiple claims.

    Args:
        claims: List of claims to verify

    Returns:
        List of Verdict objects
    """
    logger.info("factchecker_started", num_claims=len(claims))

    verdicts = []
    for i, claim in enumerate(claims):
        # Generate claim_id if not present
        if not claim.claim_id:
            claim.claim_id = hashlib.sha256(claim.text.encode()).hexdigest()[:16]

        verdict = await verify_claim(claim, i)
        verdicts.append(verdict)

    # Summary stats
    supported = sum(1 for v in verdicts if v.verdict == VerdictType.SUPPORTED)
    refuted = sum(1 for v in verdicts if v.verdict == VerdictType.REFUTED)
    needs_more = sum(1 for v in verdicts if v.verdict == VerdictType.NEEDS_MORE_EVIDENCE)

    logger.info(
        "factchecker_complete",
        total_claims=len(verdicts),
        supported=supported,
        refuted=refuted,
        needs_more_evidence=needs_more,
    )

    return verdicts

