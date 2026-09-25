"""
Ablation Study Orchestrator.
Systematically evaluates 6 architectural configurations on the exact same frozen test benchmark:
1. Regex only
2. GLiNER only
3. Regex + GLiNER
4. Regex + GLiNER + Context
5. Regex + GLiNER + Context + Document Registry
6. Full Pipeline
"""

from typing import List, Dict, Any
import json
import os
from src.evaluation.metrics import MetricsCalculator
from src.detectors.regex.recognizers import RegexDetector
from src.detectors.neural.gliner_detector import GlinerDetector
from src.detectors.context.proximity_scorer import ContextProximityScorer
from src.detectors.context.address_detector import ContextualAddressDetector
from src.detectors.context.entity_registry import DocumentEntityRegistry
from src.resolution.conflict_resolver import ConflictResolver


class AblationStudyRunner:
    """Orchestrates multi-stage ablation experiments."""

    def __init__(self, model_path: str = "models/gliner_multi_pii"):
        self.regex = RegexDetector()
        self.gliner = GlinerDetector(model_path=model_path)
        self.context_scorer = ContextProximityScorer()
        self.address_detector = ContextualAddressDetector()
        self.registry = DocumentEntityRegistry()
        self.resolver = ConflictResolver()
        self.metrics_calculator = MetricsCalculator()

    def run_ablation(self, dataset_path: str) -> Dict[str, Any]:
        """Runs all 6 ablation configurations on the dataset."""
        records = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        configs = [
            {"id": "Ablation 1: Regex Only", "regex": True, "gliner": False, "context": False, "registry": False},
            {"id": "Ablation 2: GLiNER Only", "regex": False, "gliner": True, "context": False, "registry": False},
            {"id": "Ablation 3: Regex + GLiNER", "regex": True, "gliner": True, "context": False, "registry": False},
            {"id": "Ablation 4: Regex + GLiNER + Context", "regex": True, "gliner": True, "context": True, "registry": False},
            {"id": "Ablation 5: Regex + GLiNER + Context + Registry", "regex": True, "gliner": True, "context": True, "registry": True},
            {"id": "Ablation 6: Full Pipeline", "regex": True, "gliner": True, "context": True, "registry": True},
        ]

        results = {}

        for cfg in configs:
            cfg_name = cfg["id"]
            all_gold = []
            all_pred = []
            total_tokens = 0
            offset_shift = 0

            self.registry.reset()

            for rec in records:
                text = rec["text"]
                gold = rec.get("entities", [])
                total_tokens += len(text.split())

                candidates = []
                if cfg["regex"]:
                    candidates.extend(self.regex.detect(text))
                if cfg["gliner"]:
                    candidates.extend(self.gliner.detect(text))
                if cfg["context"]:
                    candidates.extend(self.address_detector.detect(text))
                    candidates = self.context_scorer.score_and_adjust(candidates, text)
                if cfg["registry"]:
                    for c in candidates:
                        self.registry.register_candidate(c)
                    prop = self.registry.propagate_to_text(text, candidates)
                    candidates.extend(prop)

                resolved = self.resolver.resolve(candidates)

                preds = [
                    {"start": s.start + offset_shift, "end": s.end + offset_shift, "label": s.type}
                    for s in resolved
                ]
                golds = [
                    {"start": g["start"] + offset_shift, "end": g["end"] + offset_shift, "label": g["label"]}
                    for g in gold
                ]

                all_pred.extend(preds)
                all_gold.extend(golds)
                offset_shift += len(text) + 100

            eval_res = self.metrics_calculator.evaluate_spans(all_gold, all_pred, total_tokens)
            results[cfg_name] = {
                "precision": eval_res["strict_micro_precision"],
                "recall": eval_res["strict_micro_recall"],
                "f1": eval_res["strict_micro_f1"],
                "macro_f1": eval_res["strict_macro_f1"],
                "accuracy": eval_res["diagnostic_accuracy"],
                "tp": eval_res["total_tp"],
                "fp": eval_res["total_fp"],
                "fn": eval_res["total_fn"]
            }

        os.makedirs("artifacts/reports", exist_ok=True)
        with open("artifacts/reports/ablation_study_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results
