"""
Benchmark Runner.
Executes evaluation passes over gold-standard JSONL datasets and computes
strict span-level Precision, Recall, F1, and diagnostic Accuracy metrics.
"""

from typing import List, Dict, Any, Optional
import json
import os
from src.evaluation.metrics import MetricsCalculator
from src.pipeline import PiiRedactionPipeline


class BenchmarkRunner:
    """Executes benchmark evaluation on dataset files."""

    def __init__(self, pipeline: Optional[PiiRedactionPipeline] = None):
        self.pipeline = pipeline or PiiRedactionPipeline()
        self.metrics_calculator = MetricsCalculator()

    def run_benchmark(self, dataset_path: str, report_name: str = "benchmark_report.json") -> Dict[str, Any]:
        """Runs the pipeline over the dataset and computes strict span metrics."""
        records = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        all_gold_spans = []
        all_pred_spans = []
        total_tokens = 0
        sample_results = []

        # Coordinate offset shift accumulator to evaluate globally
        offset_shift = 0

        for rec in records:
            text = rec["text"]
            gold = rec.get("entities", [])
            total_tokens += len(text.split())

            # Run detection on text
            candidates = []
            # 1. Regex
            candidates.extend(self.pipeline.regex_detector.detect(text))
            # 2. Neural
            if self.pipeline.neural_detector:
                candidates.extend(self.pipeline.neural_detector.detect(text))
            # 3. Context Address
            if self.pipeline.address_detector:
                candidates.extend(self.pipeline.address_detector.detect(text))
            # 4. Context Scorer
            if self.pipeline.context_scorer:
                candidates = self.pipeline.context_scorer.score_and_adjust(candidates, text)
            # 5. Entity Registry
            if self.pipeline.entity_registry:
                for c in candidates:
                    self.pipeline.entity_registry.register_candidate(c)
                propagated = self.pipeline.entity_registry.propagate_to_text(text, candidates)
                candidates.extend(propagated)

            # 6. Conflict Resolution
            resolved = self.pipeline.conflict_resolver.resolve(candidates)

            # Format predictions
            preds = [
                {
                    "start": s.start,
                    "end": s.end,
                    "label": s.type,
                    "text": s.text
                }
                for s in resolved
            ]

            sample_results.append({
                "id": rec.get("id"),
                "text": text,
                "gold": gold,
                "predictions": preds
            })

            # Accumulate with offset shifts for aggregate evaluation
            for g in gold:
                all_gold_spans.append({
                    "start": g["start"] + offset_shift,
                    "end": g["end"] + offset_shift,
                    "label": g["label"],
                    "text": g.get("text", "")
                })

            for p in preds:
                all_pred_spans.append({
                    "start": p["start"] + offset_shift,
                    "end": p["end"] + offset_shift,
                    "label": p["label"],
                    "text": p["text"]
                })

            offset_shift += len(text) + 100

        # Calculate metrics
        metrics = self.metrics_calculator.evaluate_spans(
            gold_spans=all_gold_spans,
            pred_spans=all_pred_spans,
            total_tokens=max(1, total_tokens)
        )

        full_report = {
            "dataset": dataset_path,
            "total_samples": len(records),
            "total_tokens": total_tokens,
            "metrics": metrics,
            "samples": sample_results
        }

        # Save report
        os.makedirs("artifacts/reports", exist_ok=True)
        out_path = os.path.join("artifacts/reports", report_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        return full_report
