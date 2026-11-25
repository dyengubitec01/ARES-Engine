"""청크 텍스트 품질 점수 계산.

폰트 깨짐, 인코딩 오류, 구조적 노이즈 등을 다층 신호로 점수화합니다.
"외국어 = 노이즈"가 아니라 "단편적/맥락 이탈 외국어 = 깨짐"으로 판별합니다.

주요 함수:
- score_chunk_corruption(text, doc_context): 청크별 corruption 점수
- analyze_document_consistency(chunks): 문서 단위 스크립트 일관성 분석
- get_script(char), get_category(char): 문자별 유니코드 블록/카테고리 조회
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Unicode 표준 데이터 위치 (base 소유: chunking/data/Blocks.txt, unicode.org UNIDATA)
_DATA_DIR = Path(__file__).parent / "data"
_BLOCKS_FILE = _DATA_DIR / "Blocks.txt"

# lingua-py 옵셔널 임포트 (없으면 신호 6 비활성)
try:
    from lingua import Language, LanguageDetectorBuilder
    _LINGUA_AVAILABLE = True
except ImportError:
    _LINGUA_AVAILABLE = False


# ============================================================
# 1. Unicode 블록 데이터 로딩
# ============================================================

_BLOCKS: Optional[List[Tuple[int, int, str]]] = None


def _load_blocks() -> List[Tuple[int, int, str]]:
    """Blocks.txt 1회 파싱 + 정렬된 리스트 반환 (이진 탐색용)."""
    global _BLOCKS
    if _BLOCKS is not None:
        return _BLOCKS

    blocks: List[Tuple[int, int, str]] = []
    with open(_BLOCKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                range_part, name = line.split(";", 1)
                start_hex, end_hex = range_part.split("..")
                blocks.append((int(start_hex, 16), int(end_hex, 16), name.strip()))
            except (ValueError, IndexError):
                continue

    blocks.sort(key=lambda x: x[0])
    _BLOCKS = blocks
    return _BLOCKS


@lru_cache(maxsize=65536)
def get_script(char: str) -> str:
    """문자의 유니코드 블록명 반환. 예: 'Hangul Syllables', 'Tibetan'."""
    if not char:
        return "Empty"
    cp = ord(char[0])
    blocks = _load_blocks()

    lo, hi = 0, len(blocks)
    while lo < hi:
        mid = (lo + hi) // 2
        start, end, name = blocks[mid]
        if cp < start:
            hi = mid
        elif cp > end:
            lo = mid + 1
        else:
            return name
    return "No_Block"


def get_category(char: str) -> str:
    """문자의 유니코드 General Category 반환. 예: 'Lu', 'Po', 'Cc'."""
    if not char:
        return ""
    return unicodedata.category(char[0])


# ============================================================
# 2. 한국 문서 스크립트 자연도 정의
# ============================================================

# 한국 문서에서 자연스럽게 등장 가능한 블록 (단편이어도 정상)
NATURAL_SCRIPTS: Set[str] = {
    "Basic Latin",
    "Latin-1 Supplement",
    "Hangul Jamo",
    "Hangul Compatibility Jamo",
    "Hangul Syllables",
    "Hangul Jamo Extended-A",
    "Hangul Jamo Extended-B",
    "CJK Symbols and Punctuation",
    "CJK Unified Ideographs",
    "CJK Unified Ideographs Extension A",
    "CJK Compatibility Ideographs",
    "CJK Compatibility Forms",
    "Halfwidth and Fullwidth Forms",
    "Enclosed CJK Letters and Months",
    "CJK Compatibility",
    "General Punctuation",
    "Superscripts and Subscripts",
    "Currency Symbols",
    "Letterlike Symbols",
    "Number Forms",
    "Arrows",
    "Mathematical Operators",
    "Geometric Shapes",
    "Miscellaneous Symbols",
    "Miscellaneous Symbols and Arrows",
    "Dingbats",
    "Enclosed Alphanumerics",
    "Enclosed Alphanumeric Supplement",
    "Box Drawing",
    "Block Elements",
    "Spacing Modifier Letters",
    "Vertical Forms",
    "Greek and Coptic",  # γ, α, θ, Φ, β, μ, Ω — 한국 공학/학술 문서에서 빈번한 정상 표기
}

# 조건부 자연스러움: 충분한 연속성 있을 때만 정상 (단편이면 의심)
CONDITIONAL_SCRIPTS: Set[str] = {
    "Hiragana",
    "Katakana",
    "Katakana Phonetic Extensions",
    "Cyrillic",
    "Cyrillic Supplement",
    "Combining Diacritical Marks",
    "Latin Extended-A",
    "Latin Extended-B",
    "Latin Extended Additional",
    "IPA Extensions",
    "Phonetic Extensions",
}

# 한국 문서에 거의 등장 불가능 — 등장하면 폰트 깨짐 강한 의심
SUSPICIOUS_SCRIPTS: Set[str] = {
    "Tibetan",
    "Sinhala",
    "Myanmar",
    "Khmer",
    "Lao",
    "Thai",
    "Hebrew",
    "Arabic",
    "Arabic Supplement",
    "Arabic Extended-A",
    "Arabic Extended-B",
    "Syriac",
    "Devanagari",
    "Bengali",
    "Gurmukhi",
    "Gujarati",
    "Oriya",
    "Tamil",
    "Telugu",
    "Kannada",
    "Malayalam",
    "Ethiopic",
    "Cherokee",
    "Mongolian",
    "Georgian",
    "Armenian",
    "Tifinagh",
    "Vai",
    "Bamum",
    "Coptic",
    "Glagolitic",
    "Runic",
    "Ogham",
    "Phags-pa",
    "Tagbanwa",
    "Buhid",
    "Hanunoo",
    "Tagalog",
    "Limbu",
    "Tai Le",
    "Buginese",
    "Balinese",
    "Sundanese",
    "Batak",
    "Lepcha",
    "Ol Chiki",
    "NKo",
    "Samaritan",
    "Mandaic",
    "Thaana",
}

# 항상 노이즈 (스크립트 무관)
ALWAYS_NOISE_CATEGORIES: Set[str] = {
    "Cc",  # Control (예외: \t \n \r)
    "Cf",  # Format (ZWSP, BOM 등)
    "Co",  # Private Use Area
    "Cn",  # Unassigned
    "Cs",  # Surrogate
}

# Cc 카테고리 중 보존할 문자
CC_PRESERVE = frozenset({"\t", "\n", "\r"})


# ============================================================
# 3. 청크 단위 점수 계산 (6 신호)
# ============================================================

@dataclass
class ChunkQualityScore:
    """청크 품질 점수 결과."""
    score: int
    signals: Dict[str, object] = field(default_factory=dict)
    detected_scripts: Counter = field(default_factory=Counter)
    suspicious_char_samples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "signals": dict(self.signals),
            "detected_scripts": dict(self.detected_scripts),
            "suspicious_char_samples": self.suspicious_char_samples[:20],
        }


_lingua_detector = None


def _get_lingua_detector():
    """lingua-py detector 지연 초기화."""
    global _lingua_detector
    if _lingua_detector is None and _LINGUA_AVAILABLE:
        # 한국어 + 자주 등장 가능한 외국어만 선택 (속도/정확도 균형)
        languages = [
            Language.KOREAN, Language.ENGLISH, Language.JAPANESE,
            Language.CHINESE,
        ]
        _lingua_detector = LanguageDetectorBuilder.from_languages(*languages).build()
    return _lingua_detector


def score_chunk_corruption(
    text: str,
    doc_context: Optional[Dict] = None,
) -> ChunkQualityScore:
    """청크의 corruption 점수 계산.

    Args:
        text: 청크 텍스트
        doc_context: analyze_document_consistency() 결과 (옵션, 신호 5에 사용)

    Returns:
        ChunkQualityScore — score가 클수록 의심
        - 0~2: 정상
        - 3~5: 약한 의심 (검토 권장)
        - 6+: 강한 의심 (폰트 깨짐 가능성 높음)
    """
    if not text or len(text) < 5:
        return ChunkQualityScore(score=0)

    # 문자별 분류
    script_chars: Dict[str, List[str]] = defaultdict(list)
    category_counts: Counter = Counter()
    suspicious_chars: List[str] = []

    for ch in text:
        script = get_script(ch)
        category = get_category(ch)
        script_chars[script].append(ch)
        category_counts[category] += 1

        # 의심 문자 수집: ALWAYS_NOISE 카테고리 + SUSPICIOUS 스크립트 문자 포함
        # (Devanagari/Tibetan 등 폰트 깨짐 의심 문자도 Top 빈도에 보이도록)
        if category in ALWAYS_NOISE_CATEGORIES:
            if category == "Cc" and ch in CC_PRESERVE:
                continue
            suspicious_chars.append(ch)
        elif script in SUSPICIOUS_SCRIPTS:
            suspicious_chars.append(ch)

    detected_scripts = Counter({s: len(chars) for s, chars in script_chars.items()})

    score = 0
    signals: Dict[str, object] = {}

    # ---- 신호 1: 비-자연 스크립트 다양성 ----
    non_natural = [
        s for s in detected_scripts
        if s not in NATURAL_SCRIPTS and s != "No_Block"
    ]
    signals["non_natural_script_count"] = len(non_natural)
    signals["non_natural_scripts"] = non_natural
    if len(non_natural) >= 3:
        score += 3
    elif len(non_natural) == 2:
        score += 1

    # ---- 신호 2: 단편성 (의심/조건부 스크립트가 적은 글자만 등장) ----
    fragmented = []
    for script, chars in script_chars.items():
        if script in SUSPICIOUS_SCRIPTS or script in CONDITIONAL_SCRIPTS:
            n = len(chars)
            if n < 3:
                fragmented.append(f"{script}({n})")
                # Greek 등 학술 단발은 정상일 수 있어 가중치 낮춤
                if script in {"Greek and Coptic", "Latin Extended-A", "Latin Extended-B"}:
                    score += 0
                else:
                    score += 2
    signals["fragmented_scripts"] = fragmented

    # ---- 신호 3: 알려진 깨짐 마커와 동시 등장 ----
    has_ufffd = "�" in text
    has_hex_dump = bool(re.search(r"(?:[0-9a-fA-F]{2}:){3,}", text))
    if has_ufffd:
        score += 2
        signals["has_replacement_char"] = True
    if has_hex_dump:
        score += 3
        signals["has_hex_dump"] = True

    # ---- 신호 4: 강한 의심 스크립트 등장 ----
    suspicious_present = [s for s in detected_scripts if s in SUSPICIOUS_SCRIPTS]
    if suspicious_present:
        score += 3
        signals["suspicious_scripts_present"] = suspicious_present

    # ---- 신호 5: 문서 단위 컨텍스트 (해당 문서에서 희귀한 스크립트) ----
    if doc_context and "rare_scripts" in doc_context:
        rare = doc_context["rare_scripts"]
        rare_in_chunk = [s for s in detected_scripts if s in rare]
        if rare_in_chunk:
            score += 1
            signals["doc_rare_scripts"] = rare_in_chunk

    # ---- 신호 6: 언어 감지 vs 스크립트 불일치 (lingua 사용) ----
    if _LINGUA_AVAILABLE and len(text) >= 30:
        detector = _get_lingua_detector()
        if detector:
            try:
                detected_lang = detector.detect_language_of(text)
                if detected_lang == Language.KOREAN:
                    # 한국어 청크에 의심/조건부 스크립트 단편 등장 → 깨짐 강한 신호
                    has_unexpected = any(
                        s in SUSPICIOUS_SCRIPTS or
                        (s in CONDITIONAL_SCRIPTS and len(script_chars[s]) < 3)
                        for s in detected_scripts
                    )
                    if has_unexpected:
                        score += 2
                        signals["lang_script_mismatch"] = True
                signals["detected_language"] = detected_lang.name if detected_lang else None
            except Exception:
                pass

    # ---- 노이즈 카테고리 등장 (보너스 점수) ----
    noise_count = sum(
        category_counts.get(c, 0) for c in ALWAYS_NOISE_CATEGORIES
    ) - sum(1 for ch in text if ch in CC_PRESERVE and get_category(ch) == "Cc")
    if noise_count > 0:
        score += 1
        signals["always_noise_count"] = noise_count

    return ChunkQualityScore(
        score=score,
        signals=signals,
        detected_scripts=detected_scripts,
        suspicious_char_samples=list(dict.fromkeys(suspicious_chars))[:20],
    )


# ============================================================
# 4. 문서 단위 일관성 분석
# ============================================================

def analyze_document_consistency(chunks: List[str]) -> Dict:
    """문서 내 청크들의 스크립트 일관성 분석.

    문서 단위로 어떤 스크립트가 흔하고/희귀한지 파악 → 단편성 판단의 보조 자료.

    Returns:
        {
            'chunk_count': int,
            'rare_scripts': set[str] — 5% 미만 청크에만 등장하는 비-자연 스크립트,
            'common_scripts': set[str] — 50% 이상 청크에 등장하는 스크립트,
            'script_chunk_ratio': dict[str, float],
        }
    """
    if not chunks:
        return {
            "chunk_count": 0,
            "rare_scripts": set(),
            "common_scripts": set(),
            "script_chunk_ratio": {},
        }

    script_chunk_count: Dict[str, int] = defaultdict(int)
    for chunk in chunks:
        scripts_seen: Set[str] = set()
        for ch in chunk:
            scripts_seen.add(get_script(ch))
        for script in scripts_seen:
            script_chunk_count[script] += 1

    n = len(chunks)
    script_chunk_ratio = {s: c / n for s, c in script_chunk_count.items()}

    rare_scripts = {
        s for s, r in script_chunk_ratio.items()
        if r < 0.05 and s not in NATURAL_SCRIPTS and s != "No_Block"
    }
    common_scripts = {s for s, r in script_chunk_ratio.items() if r > 0.5}

    return {
        "chunk_count": n,
        "rare_scripts": rare_scripts,
        "common_scripts": common_scripts,
        "script_chunk_ratio": script_chunk_ratio,
    }


# ============================================================
# 5. 점수 해석 헬퍼
# ============================================================

def classify_score(score: int) -> str:
    """점수 → 카테고리 라벨."""
    if score == 0:
        return "clean"
    if score <= 2:
        return "minor"
    if score <= 5:
        return "suspicious"
    return "likely_corrupted"


# ============================================================
# 6. 노이즈 문자 스트립 (cleaning 보조)
# ============================================================

def strip_noise_scripts(text: str) -> str:
    """한국어 문서에 정상적으로 등장하지 않는 노이즈 문자 제거.

    OCR/폰트 오독으로 섞여든 단발 글자(티벳/아랍/데바나가리 등 SUSPICIOUS_SCRIPTS)와
    제어·포맷·PUA·미할당·서로게이트(ALWAYS_NOISE_CATEGORIES) 문자를 제거한다.
    정상 스크립트(한글/한자/라틴/그리스/기호·표 구조 문자 등)는 보존하므로
    markdown 표 형식이나 공학 수식 표기(α, θ 등 그리스=NATURAL)에는 영향 없다.

    제거로 생긴 연속 공백은 한 칸으로 정리한다(줄바꿈은 보존).
    """
    if not text:
        return text
    out = []
    for ch in text:
        cat = get_category(ch)
        if cat in ALWAYS_NOISE_CATEGORIES and ch not in CC_PRESERVE:
            continue
        if get_script(ch) in SUSPICIOUS_SCRIPTS:
            continue
        out.append(ch)
    cleaned = "".join(out)
    # 스트립으로 생긴 과잉 공백/탭 정리 (개행은 유지)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned
