"""Critic eval: deterministic precision/recall/F1 + confidence calibration.

Parametrised over EVAL_CRITIC_MODELS × critic_cases.json. Each case has
pre-labeled claims ("supported" or "false"); the positive class is "false"
(inserted falsehood). A test only fails on infrastructure errors.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app.agents.critic import CriticAgent
from app.agents.critic_graph import run_critic
from app.models.events import ProgressEvent
from app.models.research import CriticAnnotations, ScribeReport, Verdict
from tests.evals._harness import (
    RUBRIC_RATIONALE_QUALITY,
    EvalConfig,
    judge,
    load_eval_config,
)
from tests.evals._loaders import CriticCase, load_critic_cases
from tests.evals._reporting import EvalRecorder

_CLAIM_SPAN_RE = re.compile(
    r"<span\b[^>]*\bdata-claim\s*=\s*['\"][^'\"]+['\"][^>]*>",
    re.IGNORECASE,
)

_cfg = load_eval_config()
_CASES = load_critic_cases()
_PARAMS = [(m, c) for m in _cfg.critic_models for c in _CASES]


async def _noop(_: ProgressEvent) -> None:
    """No-op event publisher; evals don't need progress events."""


@pytest.mark.agent_eval
@pytest.mark.parametrize(
    "model,case_obj",
    _PARAMS,
    ids=[f"{m.split('/')[-1]}__{c.id}" for m, c in _PARAMS],
)
async def test_critic_quality(
    model: str,
    case_obj: CriticCase,
    eval_config: EvalConfig,
    eval_recorder: EvalRecorder,
) -> None:
    agent = CriticAgent(model)
    annotations = await run_critic(
        job_id=uuid4(),
        report=case_obj.report,
        agent=agent,
        publish=_noop,
    )

    # -- deterministic metrics ------------------------------------------------
    prec, rec, f1, prf_detail = _compute_prf(annotations, case_obj.labels)
    eval_recorder.record("critic", model, case_obj.id, "hallucination_precision", prec, prf_detail)
    eval_recorder.record("critic", model, case_obj.id, "hallucination_recall", rec, prf_detail)
    eval_recorder.record("critic", model, case_obj.id, "hallucination_f1", f1, prf_detail)

    cal, cal_detail = _confidence_calibration(annotations, case_obj.labels, case_obj.report)
    eval_recorder.record("critic", model, case_obj.id, "confidence_calibration", cal, cal_detail)

    # -- LLM judge (rationale quality) ----------------------------------------
    flags_block = "\n".join(
        f"Claim {f.claim_id}: verdict={f.verdict}, rationale={f.rationale!r}"
        for f in annotations.claim_flags
    )
    source_block = "\n".join(f"[{s.id}] {s.title}: {s.snippet}" for s in case_obj.report.sources)
    rationale = await judge(
        judge_model=eval_config.judge_model,
        rubric=RUBRIC_RATIONALE_QUALITY,
        content=(
            f"Topic: {case_obj.topic}\n\n"
            f"Sources:\n{source_block}\n\n"
            f"Fact-checker verdicts and rationales:\n{flags_block}"
        ),
    )
    eval_recorder.record(
        "critic",
        model,
        case_obj.id,
        "rationale_quality",
        rationale.score,
        rationale.reasoning,
    )


# ---- metric helpers ---------------------------------------------------------


def _compute_prf(
    annotations: CriticAnnotations,
    labels: dict[str, str],
) -> tuple[float, float, float, str]:
    """Precision, recall, F1 for hallucination detection.

    Positive class = "false" (inserted falsehood). A claim is "flagged" when
    Critic assigns verdict UNSUPPORTED or CONTRADICTED. PARTIALLY_SUPPORTED
    is treated as not-flagged; the count of partial hits on false claims is
    included in `detail` for inspection.
    """
    flagged = {
        f.claim_id
        for f in annotations.claim_flags
        if f.verdict in (Verdict.UNSUPPORTED, Verdict.CONTRADICTED)
    }
    labeled_false = {cid for cid, lbl in labels.items() if lbl == "false"}

    tp = len(flagged & labeled_false)
    fp = len(flagged - labeled_false)
    fn = len(labeled_false - flagged)

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    flagged_partial = {
        f.claim_id for f in annotations.claim_flags if f.verdict == Verdict.PARTIALLY_SUPPORTED
    }
    partial_on_false = len(flagged_partial & labeled_false)
    detail = f"tp={tp} fp={fp} fn={fn} partially_supported_on_false={partial_on_false}"

    return round(prec, 4), round(rec, 4), round(f1, 4), detail


def _confidence_calibration(
    annotations: CriticAnnotations,
    labels: dict[str, str],
    report: ScribeReport,
) -> tuple[float, str]:
    """1 - mean_abs_error between Critic confidence scores and ground-truth good fractions.

    Computed both overall (overall_confidence vs fraction of supported labels)
    and per-section (section score vs fraction of supported labels in that section).
    """
    total = len(labels)
    supported_count = sum(1 for v in labels.values() if v == "supported")
    good_fraction = supported_count / total if total > 0 else 1.0
    overall_error = abs(annotations.overall_confidence - good_fraction)

    section_claim_ids: dict[str, set[str]] = {
        s.id: set(_CLAIM_SPAN_RE.findall(s.body_md)) for s in report.sections
    }
    section_errors: list[float] = []
    for sc in annotations.section_confidence:
        claim_ids = section_claim_ids.get(sc.section_id, set())
        sec_labeled = {cid: labels[cid] for cid in claim_ids if cid in labels}
        if not sec_labeled:
            continue
        sec_good = sum(1 for v in sec_labeled.values() if v == "supported")
        sec_good_frac = sec_good / len(sec_labeled)
        section_errors.append(abs(sc.score - sec_good_frac))

    all_errors = [overall_error, *section_errors]
    mean_mae = sum(all_errors) / len(all_errors)
    value = round(1.0 - mean_mae, 4)
    detail = (
        f"overall_conf={annotations.overall_confidence:.2f} "
        f"good_frac={good_fraction:.2f} "
        f"mae={mean_mae:.3f}"
    )
    return value, detail
