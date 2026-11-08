import pandas as pd
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)

ROOT = Path(".")
EVAL = ROOT / "docs/evaluation"
CHARTS = EVAL / "charts"
OUTPUT = ROOT / "docs/reports/RAGLab_Experimental_Evaluation.pdf"

df = pd.read_csv(EVAL / "PES1UG24AM207_configuration_comparison.csv")
df = df.sort_values("rank")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ReportTitle", parent=styles["Title"],
    fontSize=24, leading=30, alignment=TA_CENTER,
    textColor=colors.HexColor("#17365D"), spaceAfter=12
))
styles.add(ParagraphStyle(
    name="Section", parent=styles["Heading1"],
    fontSize=16, leading=20, textColor=colors.HexColor("#1F4E79"),
    spaceBefore=12, spaceAfter=8
))
styles.add(ParagraphStyle(
    name="SubSection", parent=styles["Heading2"],
    fontSize=12, leading=15, textColor=colors.HexColor("#2F5597"),
    spaceBefore=8, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="BodySmall", parent=styles["BodyText"],
    fontSize=8.5, leading=12, spaceAfter=6
))
styles.add(ParagraphStyle(
    name="Cell", parent=styles["BodyText"],
    fontSize=7, leading=9
))

doc = SimpleDocTemplate(
    str(OUTPUT), pagesize=landscape(A4),
    rightMargin=15*mm, leftMargin=15*mm,
    topMargin=15*mm, bottomMargin=15*mm
)

story = []

def para(text, style="BodySmall"):
    story.append(Paragraph(text, styles[style]))

def section(text):
    story.append(Paragraph(text, styles["Section"]))

def add_table(data, widths, font_size=8):
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B4C6E7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#EAF0F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

def add_chart(filename, width=230*mm):
    path = CHARTS / filename
    if path.exists():
        img = Image(str(path))
        img.drawWidth = width
        img.drawHeight = width * img.imageHeight / img.imageWidth
        story.append(img)
        story.append(Spacer(1, 5*mm))

# Cover and overview
story.append(Spacer(1, 18*mm))
para("RAGLab AI", "ReportTitle")
para("Experimental Evaluation Report", "ReportTitle")
story.append(Spacer(1, 8*mm))
para("<b>Comparative Analysis of Chunking Strategies and Embedding Models for RAG Retrieval</b>", "Heading2")
story.append(Spacer(1, 8*mm))
para("<b>Student:</b> Priyanka B M")
para("<b>SRN:</b> PES1UG24AM207")
para("<b>Benchmark run ID:</b> 4a7b2bb4-70e1-4100-bdfc-b200b94843d1")
para("<b>Dataset ID:</b> 35ea593c-637b-42e7-810b-96647a56a617")
para("<b>Run status:</b> Completed — 18/18 configurations; 72/72 measurements; 0 failures")
story.append(Spacer(1, 10*mm))
para(
    "This report documents an exploratory retrieval benchmark comparing three "
    "chunking strategies, two embedding models and three chunk-size settings. "
    "It summarizes the recorded measurements, configuration rankings, methodology "
    "and limitations."
)
story.append(PageBreak())

# Experimental design
section("1. Experimental Design")
para(
    "The experiment compared Fixed, Sentence and Semantic chunking strategies "
    "using all-MiniLM-L6-v2 and bge-small-en-v1.5 embedding models. Each strategy "
    "and model combination was evaluated at chunk sizes of 64, 128 and 256 words, "
    "giving 18 configurations in total."
)
add_table([
    ["Experiment dimension", "Values"],
    ["Chunking strategies", "Fixed, Sentence, Semantic"],
    ["Embedding models", "all-MiniLM-L6-v2, bge-small-en-v1.5"],
    ["Chunk sizes", "64, 128, 256 words"],
    ["Total configurations", "18"],
    ["Top-k", "3"],
    ["Repetitions", "1"],
    ["Validation questions", "4 (3 answerable, 1 unanswerable)"],
], [65*mm, 180*mm])

section("2. Dataset and Evaluation Scope")
para(
    "The dataset contains 12 questions: four training, four validation and four "
    "test questions. Ten are answerable and two are unanswerable. All 12 questions "
    "were manually reviewed, with zero rejected. This benchmark used only the "
    "four validation questions, of which three were answerable."
)
para(
    "<b>Important:</b> The source document is a fictional sample campus document. "
    "It does not represent actual PES University policies. The results are "
    "exploratory and should not be generalized to real institutional documents."
)

section("3. Evaluation Metrics")
add_table([
    ["Metric", "Meaning"],
    ["Precision@3", "Relevant retrieved passages among the three requested results."],
    ["Recall@3", "Fraction of distinct validated evidence spans covered in the top three."],
    ["MRR", "Reciprocal rank of the first relevant passage, averaged over answerable questions."],
    ["Retrieval latency", "Measured query embedding, index validation/load and search time."],
    ["Indexing time", "Time recorded to build the retrieval index."],
    ["Abstention rate", "Separate measure for declining retrieval on unanswerable questions."],
], [48*mm, 197*mm])

section("4. Aggregate Results")
para(
    "The following tables report simple averages across the configurations in "
    "each group. They are descriptive summaries, not statistical significance tests."
)

model = df.groupby("model").agg(
    precision=("precision_at_3", "mean"),
    recall=("recall_at_3", "mean"),
    mrr=("mrr", "mean"),
    latency=("latency_mean_ms", "mean"),
    indexing=("indexing_time_ms", "mean")
).reset_index()

strategy = df.groupby("strategy").agg(
    precision=("precision_at_3", "mean"),
    recall=("recall_at_3", "mean"),
    mrr=("mrr", "mean"),
    latency=("latency_mean_ms", "mean"),
    indexing=("indexing_time_ms", "mean")
).reset_index()

chunk = df.groupby("chunk_words").agg(
    precision=("precision_at_3", "mean"),
    recall=("recall_at_3", "mean"),
    mrr=("mrr", "mean"),
    latency=("latency_mean_ms", "mean"),
    indexing=("indexing_time_ms", "mean")
).reset_index()

def aggregate_table(frame, label):
    rows = [[label, "Precision@3", "Recall@3", "MRR",
             "Latency (ms)", "Indexing (ms)"]]
    for _, r in frame.iterrows():
        rows.append([
            str(r.iloc[0]),
            f'{r["precision"]:.4f}',
            f'{r["recall"]:.4f}',
            f'{r["mrr"]:.4f}',
            f'{r["latency"]:.2f}',
            f'{r["indexing"]:.2f}'
        ])
    add_table(rows, [42*mm, 37*mm, 37*mm, 30*mm, 43*mm, 43*mm], 7)

para("4.1 Results by embedding model", "SubSection")
aggregate_table(model, "Model")
para("4.2 Results by chunking strategy", "SubSection")
aggregate_table(strategy, "Strategy")
para("4.3 Results by chunk size", "SubSection")
aggregate_table(chunk, "Chunk words")

story.append(PageBreak())

# Charts
section("5. Visual Analysis")
para("5.1 Average retrieval latency by embedding model", "SubSection")
add_chart("model_latency_comparison.png", 205*mm)
para("5.2 Average Precision@3 by chunking strategy", "SubSection")
add_chart("chunking_strategy_precision.png", 205*mm)
story.append(PageBreak())

para("5.3 Average retrieval latency by chunk size", "SubSection")
add_chart("chunk_size_latency.png", 205*mm)
para("5.4 Retrieval latency across all 18 configurations", "SubSection")
add_chart("all_configuration_latency.png", 245*mm)

story.append(PageBreak())

# Detailed ranking
section("6. Configuration Ranking")
para(
    "The ranking below follows the benchmark's recorded optimizer score. "
    "The optimizer score combines retrieval accuracy and normalized speed."
)
ranking_rows = [[
    "Rank", "Model", "Strategy", "Words", "P@3", "R@3", "MRR",
    "Latency ms", "Index ms", "Optimizer"
]]
for _, r in df.iterrows():
    ranking_rows.append([
        str(int(r["rank"])), str(r["model"]), str(r["strategy"]),
        str(int(r["chunk_words"])), f'{r["precision_at_3"]:.3f}',
        f'{r["recall_at_3"]:.3f}', f'{r["mrr"]:.3f}',
        f'{r["latency_mean_ms"]:.2f}', f'{r["indexing_time_ms"]:.2f}',
        f'{r["optimizer_score"]:.4f}'
    ])
add_table(ranking_rows, [
    12*mm, 35*mm, 28*mm, 16*mm, 18*mm, 18*mm,
    18*mm, 27*mm, 25*mm, 25*mm
], 6.5)

section("7. Best-ranked Configuration")
best = df.iloc[0]
para(
    f'<b>Rank 1:</b> {best["model"]}, {best["strategy"]} chunking, '
    f'{int(best["chunk_words"])} words.'
)
para(
    f'Precision@3: {best["precision_at_3"]:.4f}; '
    f'Recall@3: {best["recall_at_3"]:.4f}; '
    f'MRR: {best["mrr"]:.4f}; '
    f'Mean retrieval latency: {best["latency_mean_ms"]:.2f} ms; '
    f'Indexing time: {best["indexing_time_ms"]:.2f} ms; '
    f'Optimizer score: {best["optimizer_score"]:.4f}.'
)
para(
    "This is the best-ranked configuration under the benchmark's defined "
    "optimizer, not proof that it is universally best for other datasets."
)

section("8. Interpretation")
para(
    "All 18 configurations recorded Recall@3 and MRR of 1.0 in this small "
    "validation run. Precision@3 was generally 0.3333, with two configurations "
    "at 0.4444. These values indicate that the evaluated evidence was retrieved "
    "within the top three, while additional retrieved passages were not always "
    "relevant. The small number of answerable questions makes these metrics "
    "sensitive to individual examples."
)
para(
    "MiniLM had a lower descriptive average retrieval latency than BGE-small "
    "in this run. Fixed chunking had the highest average Precision@3 among the "
    "three strategies, while semantic chunking had higher average indexing time. "
    "These are observations from this sample and configuration, not general "
    "claims about the models or chunking methods."
)

section("9. Methodology and Scoring")
para(
    "Optimizer retrieval accuracy = 0.45 × Recall + 0.35 × MRR + 0.20 × Precision. "
    "Speed score = 1 − (mean latency − cohort minimum) / (cohort maximum − cohort "
    "minimum). Balanced score = 0.70 × retrieval accuracy + 0.30 × speed score. "
    "Indexing time is reported separately and excluded from the speed score."
)
para(
    "Precision uses the requested k as denominator; missing ranks count as "
    "non-relevant. Recall measures coverage of distinct validated evidence spans. "
    "MRR uses the first relevant passage for answerable questions. Unanswerable "
    "questions are assessed separately through abstention rate."
)

section("10. Limitations")
for item in [
    "Only four validation questions were used, including three answerable questions.",
    "The benchmark used one repetition.",
    "The dataset is a fictional sample and is not representative of a real university knowledge base.",
    "Results are exploratory point estimates; no statistical significance is established.",
    "Answer generation was disabled; exact-match and groundedness were not evaluated.",
    "Retrieval performance does not establish generated-answer correctness.",
    "Hardware, caching and runtime conditions can affect latency."
]:
    para("• " + item)

section("11. Conclusion and Future Work")
para(
    "The benchmark completed all 18 configurations and recorded 72 measurements "
    "without failures. Under the current optimizer, MiniLM with Sentence chunking "
    "at 128 words ranked first. However, the small validation sample means the "
    "result should be treated as preliminary. Future evaluation should use a "
    "larger independently reviewed dataset, more repetitions, a held-out test "
    "set, and a separate evaluation of generated answer correctness and grounding."
)

section("12. Reproducibility References")
for item in [
    "docs/verification/PES1UG24AM207_benchmark_export.json",
    "docs/evaluation/PES1UG24AM207_configuration_comparison.csv",
    "docs/evaluation/PES1UG24AM207_aggregate_analysis.md",
    "docs/evaluation/PES1UG24AM207_REPRODUCIBILITY_NOTES.md"
]:
    para("• " + item)

def footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(15*mm, 8*mm, "RAGLab AI | PES1UG24AM207")
    canvas.drawRightString(landscape(A4)[0] - 15*mm, 8*mm,
                           f"Page {document.page}")
    canvas.restoreState()

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(f"PDF created: {OUTPUT}")
print(f"Size: {OUTPUT.stat().st_size:,} bytes")
