# ResumeLens labelling rubric

This rubric defines `human_score` in `pairs.csv`: **how well does this resume fit this job
description, judged as a recruiter screening for an interview?** Score 0 to 100. Labels are
the ground truth the evaluation script measures ResumeLens against, so consistency matters
more than precision.

## 1. Building the dataset

1. Aim for **about 50 pairs** (the script refuses to run below 10 and warns below 30).
2. Use **10 to 20 resumes** and **10 to 20 JDs**, and pair them so each resume appears with
   several JDs of differing fit. This spreads labels across the whole 0-100 range, which
   correlation metrics need. Deliberately include clear mismatches (e.g. backend resume vs
   data-science JD) and near-perfect fits.
3. Resumes: use your own, friends' (with explicit permission), or public sample resumes.
   **Never commit real people's resumes**: keep them in `evaluation/data/`, which is
   git-ignored. Text-based PDFs only; scanned PDFs are rejected by the parser.
4. JDs: copy real postings into `.txt` files (100-15,000 characters).
5. Copy `pairs_template.csv` to `pairs.csv`. Paths are relative to the CSV file. Rows whose
   `pair_id` starts with `EXAMPLE` are ignored; delete them or leave them.
6. **Label before you look at ResumeLens's output for that pair**, otherwise your labels
   will drift toward the model and inflate the results.

## 2. Score anchors

Read the JD first and note its must-haves. Then read the resume and pick the closest anchor;
use values in between (e.g. 60) when a pair falls between two anchors.

| Score | Meaning | Typical evidence |
|---:|---|---|
| **0** | No fit. Different field or role. | Almost none of the required skills; experience unrelated to the role's work. |
| **25** | Weak fit. Same broad field, wrong role. | A few overlapping skills, but most must-haves missing or the seniority is far off. |
| **50** | Partial fit. Plausible but with clear gaps. | About half the must-haves shown; relevant work but in a different stack or domain. |
| **75** | Strong fit. Would likely interview. | Most must-haves demonstrated in experience or projects; only minor or nice-to-have gaps. |
| **100** | Ideal fit. | All must-haves demonstrated with concrete evidence, plus several nice-to-haves; seniority matches. |

## 3. Consistency rules

- **Must-haves dominate.** A missing must-have caps the score at about 60 regardless of
  everything else; two or more missing caps it at about 40.
- **Evidence beats listing.** A skill shown in an experience or project bullet counts more
  than the same skill only listed in a Skills section.
- **Ignore formatting and writing quality.** Judge fit, not polish: ResumeLens's suggestions
  handle polish separately.
- **Ignore protected attributes** (name, gender, age, nationality, photo). They must not
  affect the score.
- **Seniority.** Treat a large mismatch (e.g. student resume vs "8+ years" JD) as a missing
  must-have.
- **Don't reward keyword stuffing.** A long skills list with no supporting experience is at
  most a partial fit.
- Label in one or two sittings, and **re-label the first 5 pairs at the end**; if your scores
  moved by more than about 10 points, revisit those pairs.

## 4. Two labellers and agreement (recommended)

One person's labels mix the model's errors with that person's quirks. With two labellers:

1. Each labeller scores every pair **independently**, without discussion.
2. Add an optional `human_score_2` column to `pairs.csv`:

   ```csv
   pair_id,resume_pdf,jd_txt,human_score,human_score_2
   P001,data/resumes/r01.pdf,data/jds/j01.txt,70,80
   ```

3. `evaluate.py` then evaluates against the **mean** of the two labels and reports
   inter-rater agreement:
   - **Pearson r** between the two labellers' raw scores.
   - **Quadratic-weighted Cohen's κ** after binning each score to the nearest rubric anchor
     (0/25/50/75/100). Quadratic weighting treats a 75-vs-100 disagreement as smaller than a
     0-vs-100 one. Rough reading: κ < 0.4 poor, 0.4 to 0.6 moderate, 0.6 to 0.8 substantial,
     above 0.8 near-perfect agreement.
4. If agreement is poor (κ below about 0.4), discuss the pairs with the largest
   disagreements, refine the rubric, and re-label. Do not just average away a broken rubric.

Human-human agreement is a useful ceiling when you interpret the model's Spearman ρ: the
model is unlikely to agree with the averaged label much better than the labellers agree
with each other.

## 5. What to record

Keep a short labelling log (date, labeller, anything ambiguous) next to `pairs.csv`. When you
describe the results anywhere, state the number of pairs, how they were collected, and
whether labels came from one or two people.
