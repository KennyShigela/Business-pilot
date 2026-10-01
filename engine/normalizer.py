"""
Data Normalization & Entity Matching Engine for BusinessPilot.
Identifies potential duplicate entities (e.g. 'Coke 500ml' vs 'Coca-Cola 500ml')
and suggests merges with confidence scores without destructive silent merges.
"""
import re
from typing import List, Dict, Any, Tuple


class EntityNormalizer:
    """Detects entity variations and suggests deduplication."""

    @staticmethod
    def simplify_name(name: str) -> str:
        """Strips punctuation, lowercases, and removes generic business/unit suffixes."""
        s = str(name).lower().strip()
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        # Remove common business suffixes for comparison
        suffixes = ["ltd", "limited", "inc", "corp", "co", "plc", "llc", "group"]
        words = s.split()
        filtered = [w for w in words if w not in suffixes]
        return " ".join(filtered) if filtered else s

    @classmethod
    def calculate_similarity(cls, str1: str, str2: str) -> float:
        """Token-based Jaccard and Levenshtein approximation."""
        s1 = cls.simplify_name(str1)
        s2 = cls.simplify_name(str2)

        if s1 == s2:
            return 1.0

        # Substring / abbreviation check
        if s1 in s2 or s2 in s1:
            return 0.90

        tokens1 = set(s1.split())
        tokens2 = set(s2.split())

        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))

        jaccard = intersection / max(1, union)
        return round(jaccard, 2)

    @classmethod
    def find_potential_merges(cls, names: List[str], threshold: float = 0.70) -> List[Dict[str, Any]]:
        """
        Scans a list of unique names (products, customers, vendors)
        and detects potential duplicate representations.
        """
        suggestions = []
        unique_names = list(set(filter(None, names)))
        n = len(unique_names)

        for i in range(n):
            for j in range(i + 1, n):
                name1 = unique_names[i]
                name2 = unique_names[j]
                sim = cls.calculate_similarity(name1, name2)

                if sim >= threshold:
                    suggestions.append({
                        "original_name": name1,
                        "candidate_match": name2,
                        "confidence_score": sim,
                        "suggested_action": "MERGE" if sim >= 0.85 else "REVIEW",
                        "requires_confirmation": True
                    })

        return sorted(suggestions, key=lambda x: x["confidence_score"], reverse=True)
