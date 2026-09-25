"""
Conflict Resolution and Span Arbitration Engine.
Resolves overlapping, nested, and conflicting candidate entity spans.
"""

from typing import List, Dict
from src.detectors.base import EntitySpan


class ConflictResolver:
    """Arbitrates conflicts and produces a non-overlapping set of validated PII spans."""

    TYPE_PRIORITY = {
        "EMAIL": 100,
        "CREDIT_CARD": 95,
        "IP_ADDRESS": 90,
        "SSN_TAX_ID": 85,
        "PHONE": 80,
        "ADDRESS": 70,
        "ORGANIZATION": 60,
        "PERSON": 50,
        "DATE_OF_BIRTH": 45,
    }

    def resolve(self, candidate_spans: List[EntitySpan]) -> List[EntitySpan]:
        """
        Resolves conflicts across candidate spans:
        1. Exact duplicate span merging
        2. Containment resolution (e.g., PERSON inside ORGANIZATION or ADDRESS)
        3. Partial overlap arbitration
        """
        if not candidate_spans:
            return []

        # 1. Deduplicate identical spans (start, end)
        span_map: Dict[tuple, EntitySpan] = {}
        for s in candidate_spans:
            key = (s.start, s.end)
            if key not in span_map:
                span_map[key] = s
            else:
                existing = span_map[key]
                # Merge detector sources
                for src in s.detector_sources:
                    if src not in existing.detector_sources:
                        existing.detector_sources.append(src)
                # Keep higher priority type or higher confidence
                s_prio = self.TYPE_PRIORITY.get(s.type, 0)
                ext_prio = self.TYPE_PRIORITY.get(existing.type, 0)
                if s_prio > ext_prio or (s_prio == ext_prio and s.confidence > existing.confidence):
                    span_map[key] = s

        unique_spans = list(span_map.values())

        # Sort spans by start offset, and then by descending length
        sorted_spans = sorted(unique_spans, key=lambda x: (x.start, -(x.end - x.start)))

        resolved: List[EntitySpan] = []

        for candidate in sorted_spans:
            should_add = True
            discard_indices = []

            for idx, accepted in enumerate(resolved):
                # Check for overlap
                if max(candidate.start, accepted.start) < min(candidate.end, accepted.end):
                    # Overlap detected!
                    
                    # Case A: Accepted contains candidate
                    if accepted.contains(candidate):
                        # If accepted is ORGANIZATION and candidate is PERSON, keep ORGANIZATION
                        if accepted.type == "ORGANIZATION" and candidate.type == "PERSON":
                            should_add = False
                            break
                        # If accepted is ADDRESS and candidate is PERSON/ORG/city, keep ADDRESS
                        if accepted.type == "ADDRESS":
                            should_add = False
                            break
                        # If accepted has higher or equal priority, drop candidate
                        if self.TYPE_PRIORITY.get(accepted.type, 0) >= self.TYPE_PRIORITY.get(candidate.type, 0):
                            should_add = False
                            break
                        else:
                            # Candidate has higher priority (e.g. EMAIL or PHONE inside ADDRESS)
                            # Keep both or split? Standard: structured takes priority
                            discard_indices.append(idx)

                    # Case B: Candidate contains accepted
                    elif candidate.contains(accepted):
                        if candidate.type == "ORGANIZATION" and accepted.type == "PERSON":
                            discard_indices.append(idx)
                        elif candidate.type == "ADDRESS" and accepted.type in ["PERSON", "ORGANIZATION"]:
                            discard_indices.append(idx)
                        elif self.TYPE_PRIORITY.get(candidate.type, 0) >= self.TYPE_PRIORITY.get(accepted.type, 0):
                            discard_indices.append(idx)
                        else:
                            should_add = False
                            break

                    # Case C: Partial overlap
                    else:
                        cand_prio = self.TYPE_PRIORITY.get(candidate.type, 0)
                        acc_prio = self.TYPE_PRIORITY.get(accepted.type, 0)
                        if cand_prio > acc_prio:
                            discard_indices.append(idx)
                        elif cand_prio < acc_prio:
                            should_add = False
                            break
                        else:
                            # Equal priority: keep longer span
                            cand_len = candidate.end - candidate.start
                            acc_len = accepted.end - accepted.start
                            if cand_len > acc_len:
                                discard_indices.append(idx)
                            else:
                                should_add = False
                                break

            if should_add:
                # Remove discarded indices in reverse order
                for d_idx in sorted(discard_indices, reverse=True):
                    resolved.pop(d_idx)
                resolved.append(candidate)

        # Final sort by start position
        return sorted(resolved, key=lambda x: x.start)
