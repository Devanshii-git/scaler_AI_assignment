"""
Evaluation Metrics Calculator.
Computes strict and relaxed span-level Precision, Recall, F1, and diagnostic Accuracy.
Provides per-class, micro-averaged, and macro-averaged metrics.
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict


class MetricsCalculator:
    """Calculates evaluation metrics comparing predicted spans against gold spans."""

    def __init__(self, target_classes: List[str] = None):
        self.target_classes = target_classes or [
            "PERSON", "EMAIL", "PHONE", "ORGANIZATION", "ADDRESS",
            "SSN_TAX_ID", "CREDIT_CARD", "DATE_OF_BIRTH", "IP_ADDRESS"
        ]

    def evaluate_spans(
        self,
        gold_spans: List[Dict[str, Any]],
        pred_spans: List[Dict[str, Any]],
        total_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Evaluates predictions against gold annotations using strict span matching.
        A prediction is a True Positive iff start, end, and label match exactly.
        """
        # Group by label
        class_stats = {
            cls: {"tp": 0, "fp": 0, "fn": 0, "relaxed_tp": 0}
            for cls in self.target_classes
        }

        matched_gold_indices = set()
        matched_pred_indices = set()

        # Strict Matching Pass
        for p_idx, p in enumerate(pred_spans):
            p_start = p["start"]
            p_end = p["end"]
            p_label = p["label"]

            found_match = False
            for g_idx, g in enumerate(gold_spans):
                if g_idx in matched_gold_indices:
                    continue
                if (
                    g["start"] == p_start
                    and g["end"] == p_end
                    and g["label"] == p_label
                ):
                    matched_gold_indices.add(g_idx)
                    matched_pred_indices.add(p_idx)
                    if p_label in class_stats:
                        class_stats[p_label]["tp"] += 1
                        class_stats[p_label]["relaxed_tp"] += 1
                    found_match = True
                    break

        # Relaxed matching diagnostic (overlap > 0 with matching label)
        for p_idx, p in enumerate(pred_spans):
            if p_idx in matched_pred_indices:
                continue
            p_label = p["label"]
            for g_idx, g in enumerate(gold_spans):
                if g["label"] == p_label:
                    if max(p["start"], g["start"]) < min(p["end"], g["end"]):
                        if p_label in class_stats:
                            class_stats[p_label]["relaxed_tp"] += 1
                        break

        # Count False Positives (unmatched predictions)
        for p_idx, p in enumerate(pred_spans):
            if p_idx not in matched_pred_indices:
                p_label = p["label"]
                if p_label in class_stats:
                    class_stats[p_label]["fp"] += 1

        # Count False Negatives (unmatched gold spans)
        for g_idx, g in enumerate(gold_spans):
            if g_idx not in matched_gold_indices:
                g_label = g["label"]
                if g_label in class_stats:
                    class_stats[g_label]["fn"] += 1

        # Calculate per-class metrics
        per_class_results = {}
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_relaxed_tp = 0

        for cls, s in class_stats.items():
            tp = s["tp"]
            fp = s["fp"]
            fn = s["fn"]
            rtp = s["relaxed_tp"]

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            rel_f1 = (2 * (rtp / (rtp + fp)) * (rtp / (rtp + fn))) / ((rtp / (rtp + fp)) + (rtp / (rtp + fn))) if ((rtp + fp) > 0 and (rtp + fn) > 0 and (rtp / (rtp + fp) + rtp / (rtp + fn)) > 0) else 0.0

            per_class_results[cls] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "relaxed_f1": round(rel_f1, 4),
                "support": tp + fn
            }

            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_relaxed_tp += rtp

        # Global Micro metrics
        micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        micro_f1 = (2 * micro_prec * micro_rec) / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0.0

        # Global Macro metrics (unweighted mean across active classes)
        active_classes = [c for c in per_class_results.values() if c["support"] > 0 or c["fp"] > 0]
        if active_classes:
            macro_prec = sum(c["precision"] for c in active_classes) / len(active_classes)
            macro_rec = sum(c["recall"] for c in active_classes) / len(active_classes)
            macro_f1 = sum(c["f1"] for c in active_classes) / len(active_classes)
        else:
            macro_prec, macro_rec, macro_f1 = 0.0, 0.0, 0.0

        # Diagnostic Token-Level Accuracy
        # In token classification, TN = total_tokens - (TP + FP + FN)
        tn = max(0, total_tokens - (total_tp + total_fp + total_fn))
        accuracy = (total_tp + tn) / total_tokens if total_tokens > 0 else 0.0

        return {
            "strict_micro_precision": round(micro_prec, 4),
            "strict_micro_recall": round(micro_rec, 4),
            "strict_micro_f1": round(micro_f1, 4),
            "strict_macro_precision": round(macro_prec, 4),
            "strict_macro_recall": round(macro_rec, 4),
            "strict_macro_f1": round(macro_f1, 4),
            "diagnostic_accuracy": round(accuracy, 4),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "per_class": per_class_results
        }
