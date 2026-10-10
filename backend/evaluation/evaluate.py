"""Evaluate ResumeLens scores against human labels.

For every labelled resume/JD pair this computes four scores with the production code:

    tfidf_baseline   keyword_overlap signal alone (TF-IDF cosine, rescaled)
    embedding_only   semantic_similarity signal alone (sentence embeddings, rescaled)
    skills_only      skill_coverage signal alone (0 when the JD has no detectable skills)
    combined         the production overall_score

and reports Spearman (with a bootstrap 95% CI), Pearson and MAE against ``human_score``,
an ablation (combined score with each signal dropped in turn) and, with ``--tune``, a
weight search on a training split that is reported only on a held-out test split.

Usage (from the backend/ directory, with the virtualenv active):

    python evaluation/evaluate.py --pairs evaluation/pairs.csv
    python evaluation/evaluate.py --pairs evaluation/pairs.csv --tune --test-size 0.3 --seed 42

Outputs (in --out-dir, default evaluation/): results.md, results.csv, per_pair_scores.csv.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import logging
import math
import sys
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import stats

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings, get_settings  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.services.analyzer import ResumeAnalyzer  # noqa: E402
from app.services.scorer import Weights, combine  # noqa: E402

MIN_PAIRS = 10
WARN_PAIRS = 30
MIN_TEST_PAIRS = 10
REQUIRED_COLUMNS = ("pair_id", "resume_pdf", "jd_txt", "human_score")
EXAMPLE_PREFIX = "EXAMPLE"
RUBRIC_ANCHORS = np.array([0, 25, 50, 75, 100])

METHOD_DESCRIPTIONS = {
    "tfidf_baseline": "TF-IDF cosine only (keyword_overlap)",
    "embedding_only": "Sentence-embedding similarity only (semantic_similarity)",
    "skills_only": "Weighted skill coverage only (skill_coverage)",
    "combined": "Production overall_score",
}


class EvaluationError(Exception):
    """Fatal problem with the input data; the script exits with status 2."""


# --------------------------------------------------------------------------- data
@dataclass(frozen=True)
class Pair:
    pair_id: str
    resume_pdf: Path
    jd_txt: Path
    human_score: float
    human_score_2: float | None = None

    @property
    def target(self) -> float:
        """Label used for evaluation: the mean when a second labeller scored the pair."""
        if self.human_score_2 is None:
            return self.human_score
        return (self.human_score + self.human_score_2) / 2


def _parse_score(raw: str | None, pair_id: str, column: str) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise EvaluationError(f"{pair_id}: {column} {raw!r} is not a number") from exc
    if not 0 <= value <= 100:
        raise EvaluationError(f"{pair_id}: {column} must be between 0 and 100 (got {value})")
    return value


def load_pairs(csv_path: Path) -> list[Pair]:
    """Load labelled pairs. Example rows (pair_id starting with EXAMPLE) and rows without a
    human_score are skipped. File paths are resolved relative to the CSV's directory."""
    if not csv_path.exists():
        raise EvaluationError(
            f"{csv_path} not found. Copy evaluation/pairs_template.csv to {csv_path.name} and add labelled rows."
        )
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise EvaluationError(f"{csv_path} is missing columns: {', '.join(missing)}")
        rows = list(reader)

    base = csv_path.parent
    pairs: list[Pair] = []
    seen: set[str] = set()
    missing_files: list[str] = []
    for row in rows:
        pair_id = (row.get("pair_id") or "").strip()
        if not pair_id or pair_id.upper().startswith(EXAMPLE_PREFIX):
            continue
        if pair_id in seen:
            raise EvaluationError(f"Duplicate pair_id {pair_id!r}")
        seen.add(pair_id)
        score = _parse_score(row.get("human_score"), pair_id, "human_score")
        if score is None:
            continue
        resume = (base / row["resume_pdf"].strip()).resolve()
        jd = (base / row["jd_txt"].strip()).resolve()
        for path in (resume, jd):
            if not path.is_file():
                missing_files.append(f"{pair_id}: {path}")
        pairs.append(
            Pair(
                pair_id=pair_id,
                resume_pdf=resume,
                jd_txt=jd,
                human_score=score,
                human_score_2=_parse_score(row.get("human_score_2"), pair_id, "human_score_2"),
            )
        )
    if missing_files:
        raise EvaluationError("Files not found:\n  " + "\n  ".join(missing_files))
    return pairs


def check_pair_count(n: int) -> list[str]:
    """Refuse fewer than MIN_PAIRS; warn below WARN_PAIRS."""
    if n < MIN_PAIRS:
        raise EvaluationError(
            f"Only {n} labelled pairs found; at least {MIN_PAIRS} are required (about 50 recommended). "
            "Correlations on fewer pairs are meaningless."
        )
    if n < WARN_PAIRS:
        return [
            f"Only {n} labelled pairs: confidence intervals will be wide. Label at least {WARN_PAIRS} "
            "(ideally ~50) before quoting results."
        ]
    return []


# ------------------------------------------------------------------------ signals
@dataclass(frozen=True)
class PairSignals:
    pair_id: str
    target: float
    coverage: float | None  # None when the JD has no detectable skills
    semantic: float
    keyword: float


def compute_pair_signals(
    pairs: list[Pair], analyzer: ResumeAnalyzer, log: Callable[[str], None] = print
) -> tuple[list[PairSignals], list[str]]:
    """Run the production pipeline on every pair. Pairs that fail validation are skipped."""
    results: list[PairSignals] = []
    failures: list[str] = []
    for i, pair in enumerate(pairs, start=1):
        try:
            jd_text = analyzer.validate_jd(pair.jd_txt.read_text(encoding="utf-8"))
            resume = analyzer.prepare_resume_pdf(pair.resume_pdf.read_bytes())
            jd = analyzer.prepare_jd(jd_text)
            signals = analyzer.compute_signals(resume, jd)
        except AppError as exc:
            failures.append(f"{pair.pair_id}: {exc.code}: {exc.message}")
            log(f"  [{i}/{len(pairs)}] {pair.pair_id}: SKIPPED ({exc.code})")
            continue
        results.append(
            PairSignals(
                pair_id=pair.pair_id,
                target=pair.target,
                coverage=signals.coverage,
                semantic=signals.semantic,
                keyword=signals.keyword,
            )
        )
        log(f"  [{i}/{len(pairs)}] {pair.pair_id}: ok")
    return results, failures


ScoreFn = Callable[[PairSignals], float]


def combined_fn(weights: Weights) -> ScoreFn:
    return lambda s: combine(s.coverage, s.semantic, s.keyword, weights).overall


def method_functions(weights: Weights) -> dict[str, ScoreFn]:
    return {
        "tfidf_baseline": lambda s: s.keyword,
        "embedding_only": lambda s: s.semantic,
        "skills_only": lambda s: s.coverage if s.coverage is not None else 0.0,
        "combined": combined_fn(weights),
    }


def ablation_functions(weights: Weights) -> dict[str, ScoreFn]:
    variants = {
        "combined_without_skill_coverage": Weights(0.0, weights.semantic, weights.keyword),
        "combined_without_semantic_similarity": Weights(weights.skill, 0.0, weights.keyword),
        "combined_without_keyword_overlap": Weights(weights.skill, weights.semantic, 0.0),
    }
    out: dict[str, ScoreFn] = {"combined (all signals)": combined_fn(weights)}
    for name, w in variants.items():
        if w.skill + w.semantic + w.keyword > 0:
            out[name] = combined_fn(w)
    return out


# ------------------------------------------------------------------------ metrics
@dataclass(frozen=True)
class Metrics:
    n: int
    spearman: float
    spearman_ci_low: float
    spearman_ci_high: float
    pearson: float
    mae: float


def _safe_corr(fn: Callable, x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(fn(x, y)[0])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return _safe_corr(stats.spearmanr, x, y)


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    return _safe_corr(stats.pearsonr, x, y)


def bootstrap_spearman_ci(
    pred: np.ndarray, human: np.ndarray, n_boot: int = 2000, seed: int = 42, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile bootstrap CI: resample pairs with replacement, recompute Spearman."""
    rng = np.random.default_rng(seed)
    n = len(pred)
    values = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        value = spearman(pred[idx], human[idx])
        if not math.isnan(value):
            values.append(value)
    if len(values) < max(10, n_boot // 10):
        return float("nan"), float("nan")
    return float(np.percentile(values, 100 * alpha / 2)), float(np.percentile(values, 100 * (1 - alpha / 2)))


def evaluate_scores(pred: list[float], human: list[float], n_boot: int, seed: int) -> Metrics:
    p = np.asarray(pred, dtype=float)
    h = np.asarray(human, dtype=float)
    low, high = bootstrap_spearman_ci(p, h, n_boot, seed)
    return Metrics(
        n=len(p),
        spearman=spearman(p, h),
        spearman_ci_low=low,
        spearman_ci_high=high,
        pearson=pearson(p, h),
        mae=float(np.mean(np.abs(p - h))) if len(p) else float("nan"),
    )


def evaluate_methods(signals: list[PairSignals], fns: dict[str, ScoreFn], n_boot: int, seed: int) -> dict[str, Metrics]:
    human = [s.target for s in signals]
    return {name: evaluate_scores([fn(s) for s in signals], human, n_boot, seed) for name, fn in fns.items()}


# ------------------------------------------------------------------- agreement
def to_anchor_bins(scores: np.ndarray) -> np.ndarray:
    """Map 0-100 scores to the nearest rubric anchor index (0, 25, 50, 75, 100 -> 0..4)."""
    return np.abs(scores[:, None] - RUBRIC_ANCHORS[None, :]).argmin(axis=1)


def inter_rater_agreement(pairs: list[Pair]) -> dict[str, float] | None:
    both = [(p.human_score, p.human_score_2) for p in pairs if p.human_score_2 is not None]
    if len(both) < 3:
        return None
    from sklearn.metrics import cohen_kappa_score

    a = np.array([x for x, _ in both], dtype=float)
    b = np.array([y for _, y in both], dtype=float)
    bins_a, bins_b = to_anchor_bins(a), to_anchor_bins(b)
    if len(set(bins_a) | set(bins_b)) < 2:
        kappa = float("nan")
    else:
        kappa = float(cohen_kappa_score(bins_a, bins_b, weights="quadratic", labels=list(range(5))))
    return {
        "n": float(len(both)),
        "pearson": pearson(a, b),
        "weighted_kappa": kappa,
        "mean_abs_diff": float(np.mean(np.abs(a - b))),
    }


# ------------------------------------------------------------------------ tuning
def weight_grid(step: float) -> list[Weights]:
    steps = round(1 / step)
    grid = []
    for i, j in itertools.product(range(steps + 1), repeat=2):
        k = steps - i - j
        if k >= 0:
            grid.append(Weights(i / steps, j / steps, k / steps))
    return grid


def train_test_split(items: list, test_size: float, seed: int) -> tuple[list, list]:
    if not 0 < test_size < 1:
        raise EvaluationError("--test-size must be between 0 and 1")
    order = list(range(len(items)))
    np.random.default_rng(seed).shuffle(order)
    n_test = max(1, round(len(items) * test_size))
    test_idx = set(order[:n_test])
    train = [x for i, x in enumerate(items) if i not in test_idx]
    test = [x for i, x in enumerate(items) if i in test_idx]
    return train, test


def tune_weights(train: list[PairSignals], step: float) -> tuple[Weights, float]:
    """Grid-search weights on the training split: maximise Spearman, tie-break on MAE."""
    human = np.array([s.target for s in train], dtype=float)
    best: tuple[float, float, Weights] | None = None
    for w in weight_grid(step):
        pred = np.array([combined_fn(w)(s) for s in train], dtype=float)
        rho = spearman(pred, human)
        if math.isnan(rho):
            continue
        mae = float(np.mean(np.abs(pred - human)))
        if best is None or rho > best[0] + 1e-12 or (abs(rho - best[0]) <= 1e-12 and mae < best[1]):
            best = (rho, mae, w)
    if best is None:
        raise EvaluationError("Tuning failed: every weight setting produced constant scores on the train split.")
    return best[2], best[0]


# ----------------------------------------------------------------------- report
def fmt(value: float, digits: int = 3) -> str:
    return "n/a" if value is None or math.isnan(value) else f"{value:.{digits}f}"


def metrics_table(results: dict[str, Metrics], descriptions: dict[str, str] | None = None) -> str:
    lines = [
        "| Method | n | Spearman ρ | 95% CI (bootstrap) | Pearson r | MAE |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for name, m in results.items():
        label = f"`{name}`" + (f" — {descriptions[name]}" if descriptions and name in descriptions else "")
        ci = f"[{fmt(m.spearman_ci_low)}, {fmt(m.spearman_ci_high)}]"
        lines.append(f"| {label} | {m.n} | {fmt(m.spearman)} | {ci} | {fmt(m.pearson)} | {fmt(m.mae, 1)} |")
    return "\n".join(lines)


@dataclass
class TuningReport:
    weights: Weights
    train_spearman: float
    n_train: int
    n_test: int
    test_results: dict[str, Metrics]


def build_markdown(
    settings: Settings,
    weights: Weights,
    n_pairs: int,
    main: dict[str, Metrics],
    ablation: dict[str, Metrics],
    warnings_list: list[str],
    failures: list[str],
    agreement: dict[str, float] | None,
    tuning: TuningReport | None,
    n_boot: int,
    seed: int,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    out = [
        "# ResumeLens evaluation results",
        "",
        f"Generated {now} by `evaluation/evaluate.py`. All numbers below were measured on your labelled data.",
        "",
        "## Setup",
        "",
        f"- Labelled pairs evaluated: **{n_pairs}**" + (f" ({len(failures)} skipped)" if failures else ""),
        f"- Embedding model: `{settings.embedding_model}`; spaCy model: `{settings.spacy_model}`",
        f"- Weights (normalised): skill {weights.skill:.3f}, semantic {weights.semantic:.3f}, "
        f"keyword {weights.keyword:.3f}",
        f"- Semantic band [{settings.semantic_floor}, {settings.semantic_ceiling}], "
        f"keyword band [{settings.keyword_floor}, {settings.keyword_ceiling}]",
        f"- Bootstrap resamples: {n_boot}; seed: {seed}",
        "",
    ]
    if warnings_list:
        out += ["> **Warnings**", ">"] + [f"> - {w}" for w in warnings_list] + [""]
    out += ["## Main results", "", metrics_table(main, METHOD_DESCRIPTIONS), ""]
    out += [
        "Spearman ρ measures whether the method ranks pairs in the same order as the human labels "
        "(the main metric). Pearson r measures linear agreement. MAE is the mean absolute difference in "
        "points on the 0-100 scale and depends on the rescaling bands, so it can improve after calibration "
        "even when ranking quality does not.",
        "",
        "## Ablation (drop one signal, renormalise the remaining weights)",
        "",
        metrics_table(ablation),
        "",
    ]
    if tuning:
        w = tuning.weights
        out += [
            "## Weight tuning (train/test split)",
            "",
            f"Weights were grid-searched on {tuning.n_train} training pairs (train Spearman "
            f"{fmt(tuning.train_spearman)}) and evaluated only on {tuning.n_test} held-out test pairs.",
            "",
            f"Best weights: skill {w.skill:.2f}, semantic {w.semantic:.2f}, keyword {w.keyword:.2f}",
            "",
            metrics_table(tuning.test_results),
            "",
            "To adopt the tuned weights, set in `backend/.env`:",
            "",
            "```",
            f"WEIGHT_SKILL={w.skill:.2f}",
            f"WEIGHT_SEMANTIC={w.semantic:.2f}",
            f"WEIGHT_KEYWORD={w.keyword:.2f}",
            "```",
            "",
            "Report the **test** rows, never the training Spearman, as your result.",
            "",
        ]
    if agreement:
        out += [
            "## Inter-rater agreement",
            "",
            "| Pairs with two labels | Pearson r | Quadratic-weighted Cohen's κ (5 rubric bins) "
            "| Mean abs. difference |",
            "|---:|---:|---:|---:|",
            f"| {int(agreement['n'])} | {fmt(agreement['pearson'])} | {fmt(agreement['weighted_kappa'])} | "
            f"{fmt(agreement['mean_abs_diff'], 1)} |",
            "",
            "Human agreement is a practical ceiling: a model correlating with the averaged label about as "
            "well as the labellers correlate with each other is performing at human level on this data.",
            "",
        ]
    if failures:
        out += ["## Skipped pairs", ""] + [f"- {f}" for f in failures] + [""]
    return "\n".join(out)


def write_csvs(
    out_dir: Path,
    signals: list[PairSignals],
    fns: dict[str, ScoreFn],
    groups: dict[str, dict[str, Metrics]],
) -> None:
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["group", "method", "n", "spearman", "spearman_ci_low", "spearman_ci_high", "pearson", "mae"])
        for group, results in groups.items():
            for name, m in results.items():
                writer.writerow([group, name, m.n, m.spearman, m.spearman_ci_low, m.spearman_ci_high, m.pearson, m.mae])
    with (out_dir / "per_pair_scores.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pair_id", "human_score", *fns.keys()])
        for s in signals:
            writer.writerow([s.pair_id, s.target, *(round(fn(s), 2) for fn in fns.values())])


# ------------------------------------------------------------------------- main
def run_evaluation(
    pairs_csv: Path,
    out_dir: Path,
    analyzer: ResumeAnalyzer,
    *,
    tune: bool = False,
    test_size: float = 0.3,
    seed: int = 42,
    n_boot: int = 2000,
    grid_step: float = 0.05,
    log: Callable[[str], None] = print,
) -> str:
    """Run the full evaluation and write outputs. Returns the Markdown report."""
    settings = analyzer.settings
    pairs = load_pairs(pairs_csv)
    warnings_list = check_pair_count(len(pairs))
    log(f"Scoring {len(pairs)} labelled pairs with the production pipeline...")
    signals, failures = compute_pair_signals(pairs, analyzer, log)
    warnings_list += check_pair_count(len(signals)) if len(signals) != len(pairs) else []

    weights = analyzer.weights.normalised()
    fns = method_functions(weights)
    main = evaluate_methods(signals, fns, n_boot, seed)
    ablation = evaluate_methods(signals, ablation_functions(weights), n_boot, seed)
    groups = {"main": main, "ablation": ablation}

    tuning: TuningReport | None = None
    if tune:
        train, test = train_test_split(signals, test_size, seed)
        if len(test) < MIN_TEST_PAIRS:
            warnings_list.append(
                f"The test split has only {len(test)} pairs; tuned results are very noisy. "
                "Label more data or use a larger --test-size."
            )
        best, train_rho = tune_weights(train, grid_step)
        test_fns = {
            "combined (default weights)": combined_fn(weights),
            "combined (tuned weights)": combined_fn(best),
            "tfidf_baseline": fns["tfidf_baseline"],
            "embedding_only": fns["embedding_only"],
        }
        tuning = TuningReport(
            weights=best,
            train_spearman=train_rho,
            n_train=len(train),
            n_test=len(test),
            test_results=evaluate_methods(test, test_fns, n_boot, seed),
        )
        groups["tuning_test"] = tuning.test_results

    agreement = inter_rater_agreement(pairs)
    report = build_markdown(
        settings, weights, len(signals), main, ablation, warnings_list, failures, agreement, tuning, n_boot, seed
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.md").write_text(report, encoding="utf-8")
    write_csvs(out_dir, signals, fns, groups)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Evaluate ResumeLens against human-labelled pairs.")
    parser.add_argument("--pairs", type=Path, default=here / "pairs.csv", help="CSV of labelled pairs.")
    parser.add_argument("--out-dir", type=Path, default=here, help="Where to write results.md and CSVs.")
    parser.add_argument("--tune", action="store_true", help="Grid-search weights on a train split.")
    parser.add_argument("--test-size", type=float, default=0.3, help="Held-out fraction for --tune.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for the split and bootstrap.")
    parser.add_argument("--bootstrap", type=int, default=2000, help="Bootstrap resamples for the CI.")
    parser.add_argument("--grid-step", type=float, default=0.05, help="Weight grid step for --tune.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from app.main import build_analyzer  # imports the real embedder

    logging.getLogger().setLevel(logging.WARNING)  # keep per-request JSON logs out of the report
    settings = get_settings()
    try:
        # Fail fast on bad data before loading the embedding model.
        check_pair_count(len(load_pairs(args.pairs)))
        analyzer = build_analyzer(settings)
        analyzer.embedder.load()
        report = run_evaluation(
            args.pairs,
            args.out_dir,
            analyzer,
            tune=args.tune,
            test_size=args.test_size,
            seed=args.seed,
            n_boot=args.bootstrap,
            grid_step=args.grid_step,
        )
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print()
    print(report)
    print(f"Wrote {args.out_dir / 'results.md'}, results.csv and per_pair_scores.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
