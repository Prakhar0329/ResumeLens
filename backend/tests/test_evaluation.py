import csv
import math

import numpy as np
import pytest

from evaluation import evaluate as ev
from tests.conftest import NO_SKILL_JD, SAMPLE_JD, SAMPLE_RESUME_LINES, make_pdf

FRONTEND_RESUME = [
    "Alex Kim",
    "EXPERIENCE",
    "Frontend Developer, Pixel Labs  Jan 2022 - Present",
    "- Built React and TypeScript components used by 40,000 customers",
    "- Improved Lighthouse accessibility score from 62 to 98 with WCAG fixes",
    "- Wrote Jest and Cypress tests for the checkout flow",
    "SKILLS",
    "React, TypeScript, Next.js, Tailwind CSS, Jest, Cypress, Figma",
    "EDUCATION",
    "B.Sc. Computer Science, 2021",
]
DATA_RESUME = [
    "Priya Shah",
    "EXPERIENCE",
    "Data Analyst, Retail Co  2021 - 2024",
    "- Built forecasting models in Python with pandas and scikit-learn, cutting stockouts 18%",
    "- Created Tableau dashboards for 12 regional managers",
    "- Wrote SQL queries on BigQuery to automate weekly reporting",
    "SKILLS",
    "Python, pandas, scikit-learn, SQL, Tableau, statistics",
]
FRONTEND_JD = (
    "Frontend Engineer\nRequirements:\n- Strong React and TypeScript experience\n"
    "- Experience testing with Jest or Cypress\n- Understanding of web accessibility\n"
    "Nice to have:\n- Next.js and Tailwind CSS are a plus\n"
)
DATA_JD = (
    "Data Scientist\nRequirements:\n- Python with pandas and scikit-learn for predictive modeling\n"
    "- Strong SQL and statistics skills\n- Build dashboards in Tableau or Power BI\n"
    "Nice to have:\n- Experience with Spark is a plus\n"
)


@pytest.fixture
def dataset(tmp_path):
    """12 labelled pairs (3 resumes x 4 JDs) plus example and unlabelled rows."""
    (tmp_path / "r").mkdir()
    (tmp_path / "j").mkdir()
    resumes = {"backend": SAMPLE_RESUME_LINES, "frontend": FRONTEND_RESUME, "data": DATA_RESUME}
    jds = {"backend": SAMPLE_JD, "frontend": FRONTEND_JD, "data": DATA_JD, "reception": NO_SKILL_JD}
    for name, lines in resumes.items():
        (tmp_path / "r" / f"{name}.pdf").write_bytes(make_pdf(lines))
    for name, text in jds.items():
        (tmp_path / "j" / f"{name}.txt").write_text(text, encoding="utf-8")
    rows = [["pair_id", "resume_pdf", "jd_txt", "human_score", "human_score_2"]]
    rows.append(["EXAMPLE_001", "missing.pdf", "missing.txt", "50", ""])
    i = 0
    for r in resumes:
        for j in jds:
            i += 1
            score = 85 if r == j else (5 if j == "reception" else 30)
            second = "" if i % 2 else str(min(100, score + 10))
            rows.append([f"P{i:03d}", f"r/{r}.pdf", f"j/{j}.txt", str(score), second])
    rows.append(["P999", "r/backend.pdf", "j/backend.txt", "", ""])  # unlabelled: skipped
    path = tmp_path / "pairs.csv"
    with path.open("w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return path


def test_load_pairs_skips_examples_and_unlabelled(dataset):
    pairs = ev.load_pairs(dataset)
    assert len(pairs) == 12
    assert all(not p.pair_id.startswith("EXAMPLE") for p in pairs)
    assert pairs[1].human_score_2 is not None and pairs[1].target == (pairs[1].human_score + pairs[1].human_score_2) / 2
    assert pairs[0].resume_pdf.is_absolute()


@pytest.mark.parametrize(
    "content,message",
    [
        ("pair_id,resume_pdf,jd_txt\nP1,a,b\n", "missing columns"),
        ("pair_id,resume_pdf,jd_txt,human_score\nP1,a.pdf,b.txt,50\n", "Files not found"),
        ("pair_id,resume_pdf,jd_txt,human_score\nP1,a.pdf,b.txt,150\n", "between 0 and 100"),
        ("pair_id,resume_pdf,jd_txt,human_score\nP1,a.pdf,b.txt,high\n", "not a number"),
        ("pair_id,resume_pdf,jd_txt,human_score\nP1,a,b,1\nP1,a,b,2\n", "Duplicate"),
    ],
)
def test_load_pairs_errors(tmp_path, content, message):
    path = tmp_path / "pairs.csv"
    path.write_text(content)
    with pytest.raises(ev.EvaluationError, match=message):
        ev.load_pairs(path)


def test_missing_csv_explains_template(tmp_path):
    with pytest.raises(ev.EvaluationError, match="pairs_template.csv"):
        ev.load_pairs(tmp_path / "pairs.csv")


def test_pair_count_guard():
    with pytest.raises(ev.EvaluationError, match="at least 10"):
        ev.check_pair_count(9)
    assert ev.check_pair_count(15)
    assert ev.check_pair_count(40) == []


def test_metrics_perfect_and_constant():
    human = list(range(0, 100, 5))
    perfect = ev.evaluate_scores([h * 0.5 for h in human], human, n_boot=200, seed=1)
    assert perfect.spearman == pytest.approx(1.0)
    assert perfect.pearson == pytest.approx(1.0)
    assert perfect.spearman_ci_low == pytest.approx(1.0)
    assert perfect.mae == pytest.approx(np.mean([h * 0.5 for h in human]))
    constant = ev.evaluate_scores([50.0] * len(human), human, n_boot=100, seed=1)
    assert math.isnan(constant.spearman) and math.isnan(constant.pearson)


def test_bootstrap_ci_contains_point_estimate():
    rng = np.random.default_rng(0)
    human = rng.uniform(0, 100, 60)
    pred = human + rng.normal(0, 25, 60)
    m = ev.evaluate_scores(list(pred), list(human), n_boot=500, seed=3)
    assert m.spearman_ci_low <= m.spearman <= m.spearman_ci_high


def test_weight_grid_and_split():
    grid = ev.weight_grid(0.5)
    assert len(grid) == 6
    assert all(math.isclose(w.skill + w.semantic + w.keyword, 1.0) for w in grid)
    items = list(range(20))
    train, test = ev.train_test_split(items, 0.3, seed=7)
    assert len(test) == 6 and not set(train) & set(test) and sorted(train + test) == items
    assert ev.train_test_split(items, 0.3, seed=7) == (train, test)
    with pytest.raises(ev.EvaluationError):
        ev.train_test_split(items, 1.5, seed=7)


def test_tuning_finds_the_informative_signal():
    rng = np.random.default_rng(1)
    signals = [
        ev.PairSignals(
            f"p{i}", target=t, coverage=float(rng.uniform(0, 100)), semantic=t, keyword=float(rng.uniform(0, 100))
        )
        for i, t in enumerate(rng.uniform(0, 100, 40))
    ]
    best, rho = ev.tune_weights(signals, step=0.1)
    assert rho == pytest.approx(1.0)
    assert best.semantic == pytest.approx(1.0)


def test_inter_rater_agreement(dataset):
    agreement = ev.inter_rater_agreement(ev.load_pairs(dataset))
    assert agreement is not None
    assert agreement["n"] == 6
    assert agreement["pearson"] > 0.9
    assert agreement["mean_abs_diff"] == pytest.approx(10.0, abs=0.01)
    assert list(ev.to_anchor_bins(np.array([0, 12, 13, 60, 100]))) == [0, 0, 1, 2, 4]


def test_run_evaluation_end_to_end(dataset, analyzer, tmp_path):
    out = tmp_path / "out"
    report = ev.run_evaluation(dataset, out, analyzer, tune=True, n_boot=200, grid_step=0.25, log=lambda _: None)
    for section in ("## Main results", "## Ablation", "## Weight tuning", "## Inter-rater agreement", "Warnings"):
        assert section in report
    assert (out / "results.md").read_text(encoding="utf-8") == report
    with (out / "results.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert {r["group"] for r in rows} == {"main", "ablation", "tuning_test"}
    assert {r["method"] for r in rows if r["group"] == "main"} == set(ev.METHOD_DESCRIPTIONS)
    with (out / "per_pair_scores.csv").open() as fh:
        per_pair = list(csv.DictReader(fh))
    assert len(per_pair) == 12
    # The zero-skill JD scores 0 on skills_only, and matching pairs beat mismatches.
    by_id = {r["pair_id"]: r for r in per_pair}
    assert float(by_id["P004"]["skills_only"]) == 0.0
    assert float(by_id["P001"]["combined"]) > float(by_id["P002"]["combined"])


def test_failed_pairs_are_skipped_and_reported(dataset, analyzer, tmp_path):
    (tmp_path / "r" / "bad.pdf").write_bytes(b"not a pdf")
    with dataset.open("a", newline="") as fh:
        csv.writer(fh).writerow(["P100", "r/bad.pdf", "j/backend.txt", "40", ""])
    report = ev.run_evaluation(dataset, tmp_path / "o", analyzer, n_boot=50, log=lambda _: None)
    assert "## Skipped pairs" in report
    assert "P100: unsupported_media_type" in report


def test_refuses_when_too_few_pairs_survive(dataset, analyzer, tmp_path):
    (tmp_path / "j" / "reception.txt").write_text("too short")
    (tmp_path / "j" / "data.txt").write_text("too short")
    with pytest.raises(ev.EvaluationError, match="at least 10"):
        ev.run_evaluation(dataset, tmp_path / "o", analyzer, n_boot=50, log=lambda _: None)


def test_cli_refuses_too_few_pairs(tmp_path, capsys):
    path = tmp_path / "pairs.csv"
    path.write_text("pair_id,resume_pdf,jd_txt,human_score\n")
    assert ev.main(["--pairs", str(path), "--out-dir", str(tmp_path)]) == 2
    assert "at least 10" in capsys.readouterr().err
