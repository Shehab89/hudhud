"""Time the zero-shot NLI model on this machine, to see what a scheduled run can afford.

    python scripts/bench_zero_shot.py

Uses made-up texts of article length (headline + excerpt, about 600 characters), so it needs
no database. Prints seconds per candidate label for the settings the pipeline could use.
"""

from __future__ import annotations

import os
import platform
import statistics
import time

import torch
from transformers import pipeline

from hudhud.config import get_settings

AR = "أعلنت وزارة الصحة في المحافظة عن وصول شحنة جديدة من الأدوية والمستلزمات الطبية إلى المستشفى الرئيسي، وقال مسؤول محلي إن الشحنة تكفي لعدة أسابيع وإن توزيعها سيبدأ غدا على المراكز الصحية في المديريات. "
EN = "The health authority said a new shipment of medicines and medical supplies arrived at the main hospital, and a local official said the stock would last several weeks and be distributed to district clinics from tomorrow. "
LABELS = ["anger", "fear", "sadness", "joy", "disgust", "surprise"]
HYPOTHESIS = "The emotion expressed in this text is {}."


def texts(n: int) -> list[str]:
    return [((AR if i % 2 == 0 else EN) * 3)[:600] for i in range(n)]


def run(label: str, clf, n: int = 4, **kw) -> None:
    sample = texts(n)
    clf(sample[0], candidate_labels=LABELS, hypothesis_template=HYPOTHESIS, multi_label=True, **kw)  # warm-up
    times = []
    for text in sample:
        t = time.monotonic()
        clf(text, candidate_labels=LABELS, hypothesis_template=HYPOTHESIS, multi_label=True, **kw)
        times.append(time.monotonic() - t)
    per_text = statistics.mean(times)
    print(f"{label:<34} {per_text:6.2f} s per text  {per_text / len(LABELS):5.2f} s per label", flush=True)


def main() -> None:
    print(f"python {platform.python_version()}  torch {torch.__version__}  cpus {os.cpu_count()}")
    print(f"torch threads {torch.get_num_threads()}  interop {torch.get_num_interop_threads()}")
    model = get_settings().zero_shot_model
    clf = pipeline("zero-shot-classification", model=model, device=-1)
    run("pipeline as the code builds it", clf)
    run("batch_size=6", clf, batch_size=6)
    torch.set_num_threads(os.cpu_count() or 1)
    print(f"torch threads now {torch.get_num_threads()}")
    run("threads = cpu count, batch 6", clf, batch_size=6)
    clf.model = torch.quantization.quantize_dynamic(clf.model, {torch.nn.Linear}, dtype=torch.qint8)
    run("int8 dynamic quantisation, batch 6", clf, batch_size=6)
    clf2 = pipeline("zero-shot-classification", model=model, device=-1, torch_dtype=torch.bfloat16)
    run("bfloat16, batch 6", clf2, batch_size=6)


if __name__ == "__main__":
    main()
