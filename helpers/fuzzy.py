# helpers/fuzzy.py
"""
Fuzzy string matching utilities – mainly for event/title/session name comparison.
Core method uses Jaro-Winkler + word-level token matching.
"""

import re
import unicodedata
from typing import List, Tuple

from . import plexlog as log
from .jaro import jaro_winkler_metric   # assuming this is your Jaro-Winkler implementation

pluginid = "FUZZY MATCH"

# Tunable thresholds (can be adjusted per use-case)
LW = 2          # long word min length
MW = 2          # medium word min length
SW = 1          # short word min length

LM = 0.85       # similarity threshold for long words
MM = 0.85       # medium
SM = 0.80       # short (slightly lower tolerance)

WORD_MATCH_WEIGHT = 4.0     # how much each good word match contributes
OVERALL_BOOST_WEIGHT = 1.0  # weight of full-string Jaro-Winkler

# ───────────────────────────────────────────────
#   Core comparison function (original + improved)
# ───────────────────────────────────────────────

def compare(s1: str, s2: str, min_score: float = 0.75) -> float:
    """
    Compare two strings using word-level Jaro-Winkler + full-string fallback.
    Returns similarity score between 0.0 and 1.0.
    
    Higher score = more similar.
    """
    if not s1 or not s2:
        return 0.0

    # Normalize unicode and prepare words
    s1_norm = unicodedata.normalize('NFC', s1.strip().lower())
    s2_norm = unicodedata.normalize('NFC', s2.strip().lower())

    # Remove numbers at end (round 12, Q3, etc.)
    s1_clean = re.sub(r'\s+[0-9]+$', '', s1_norm)
    s2_clean = re.sub(r'\s+[0-9]+$', '', s2_norm)

    words1: List[str] = re.split(r'\W+', s1_clean)
    words2: List[str] = re.split(r'\W+', s2_clean)

    words1 = [w for w in words1 if w.strip()]
    words2 = [w for w in words2 if w.strip()]

    if not words1 or not words2:
        # Fallback to full string similarity
        return jaro_winkler_metric(s1_norm, s2_norm)

    matched_scores: List[float] = []

    for w1 in words1:
        best_match = 0.0
        for w2 in words2:
            sim = jaro_winkler_metric(w1, w2)
            if len(w1) >= LW and sim > LM:
                best_match = max(best_match, sim)
            elif len(w1) >= MW and sim > MM:
                best_match = max(best_match, sim)
            elif len(w1) >= SW and sim > SM:
                best_match = max(best_match, sim)
        if best_match > 0:
            matched_scores.append(best_match)

    if not matched_scores:
        # No good word matches → fall back to full-string
        full_sim = jaro_winkler_metric(s1_norm, s2_norm)
        log.Log(f"No strong word matches | '{s1}' vs '{s2}' → full sim {full_sim:.3f}", 
                pluginid, log.LL_DEBUG)
        return full_sim

    # Weighted score: matched words + full string similarity
    word_contrib = sum(matched_scores) * WORD_MATCH_WEIGHT
    full_contrib = jaro_winkler_metric(s1_norm, s2_norm) * OVERALL_BOOST_WEIGHT

    total_weight = (len(matched_scores) * WORD_MATCH_WEIGHT) + OVERALL_BOOST_WEIGHT
    score = (word_contrib + full_contrib) / total_weight

    log.Log(f"Fuzzy compare '{s1}' vs '{s2}' → score {score:.3f} "
            f"(matched {len(matched_scores)}/{len(words1)} words)", 
            pluginid, log.LL_DEBUG if score < min_score else log.LL_INFO)

    return score


# ───────────────────────────────────────────────
#   Additional utility matchers
# ───────────────────────────────────────────────

def is_similar(s1: str, s2: str, threshold: float = 0.82) -> bool:
    """Convenience: returns True if similarity >= threshold."""
    return compare(s1, s2) >= threshold


def best_match(target: str, candidates: List[str], min_score: float = 0.78) -> Tuple[Optional[str], float]:
    """
    Find the best matching string in a list of candidates.
    Returns (best_candidate, score) or (None, 0.0)
    """
    if not candidates:
        return None, 0.0

    best_score = 0.0
    best_str = None

    for cand in candidates:
        score = compare(target, cand)
        if score > best_score:
            best_score = score
            best_str = cand

    if best_score >= min_score:
        return best_str, best_score

    return None, best_score


def normalize_for_comparison(s: str) -> str:
    """
    Aggressive normalization for matching:
    - lowercase
    - remove punctuation
    - collapse spaces
    - unicode NFC
    """
    s = unicodedata.normalize('NFC', s.lower())
    s = re.sub(r'[^a-z0-9\s]', '', s)           # remove punctuation
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Simple pure-Python Levenshtein (edit) distance – useful fallback.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def normalized_levenshtein_similarity(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0–1)."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    dist = levenshtein_distance(s1, s2)
    return 1.0 - (dist / max(len(s1), len(s2)))