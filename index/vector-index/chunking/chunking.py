"""텍스트 청킹 로직"""
import logging
import re
from typing import List, Tuple, Dict, Any, Optional

from .quality_score import strip_noise_scripts

logger = logging.getLogger(__name__)

# 양식 템플릿 라인 패턴 (컴파일)
_FORM_PATTERNS = [
    re.compile(r'^[\uAC00-\uD7A3](\s{2,}[\uAC00-\uD7A3])+\s*$'),  # "대   표   자"
    re.compile(r'^\d{4}\.\s{2,}\.\s{2,}\.\s*$'),  # "2024.     .     ."
    re.compile(r'^상호또는법인\s*\|'),  # 양식 필드 라벨
    re.compile(r'(대\s{2,}표\s{2,}자|전\s*화\s*번\s*호)\s*\|'),  # 양식 필드 라벨
    re.compile(r'^\(인\)$'),  # 직인 자리
]


def _is_form_template_chunk(text: str, threshold: float = 0.5) -> bool:
    """청크 텍스트가 양식 템플릿인지 판별.

    라인 중 양식 패턴에 매칭되는 비율이 threshold 이상이면 True.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) < 3:
        return False

    form_count = 0
    for line in lines:
        # 라인을 | 로 분리하여 각 셀도 개별 검사
        cells = [c.strip() for c in line.split('|') if c.strip()]
        line_is_form = False
        for cell in cells:
            for pat in _FORM_PATTERNS:
                if pat.search(cell):
                    line_is_form = True
                    break
            if line_is_form:
                break
        if line_is_form:
            form_count += 1

    ratio = form_count / len(lines)
    return ratio >= threshold


def split_sentences_ko(text: str) -> List[str]:
    """한국어 문장 분리"""
    # 공백 정규화 (일반 공백, 탭, 전각 공백, NBSP 등)
    # \u3000: 전각 공백 (CJK)
    # \u00A0: Non-breaking space (NBSP)
    # \u2003: Em space
    # \u2002: En space
    normalized = re.sub(r"[ \t\f\v\u3000\u00A0\u2002\u2003]+", " ", text).strip()
    if not normalized:
        return []
    
    lines = [line.strip() for line in re.split(r"[\r\n]+", normalized) if line.strip()]
    sentences: List[str] = []
    pattern = re.compile(r"[^.!?]+[.!?]?")
    
    for line in lines:
        parts = [s.strip() for s in pattern.findall(line)]
        parts = [s for s in parts if s]
        if parts:
            sentences.extend(parts)
        else:
            sentences.append(line)
    
    return sentences


def build_sentence_list_with_page(
    pages: List[Tuple[int, str]]
) -> List[Tuple[str, int]]:
    """pages: [(page_no, text), ...] → [(sentence, page_no), ...]"""
    sent_with_page: List[Tuple[str, int]] = []
    for page_no, text in pages:
        sentences = split_sentences_ko(text)
        for s in sentences:
            sent_with_page.append((s, page_no))
    return sent_with_page


def chunk_by_sentences_with_page(
    pages: List[Tuple[int, str]],
    chunk_size: int = 800,
    overlap_sents: int = 2,
    min_chunk_size: int = 100,  # 최소 청크 크기 (문자 수)
    locator_type: str = "page"  # 기본값: 실제 페이지
) -> List[Dict[str, Any]]:
    """페이지 + 문장 기반 청킹"""
    sent_with_page = build_sentence_list_with_page(pages)
    chunks: List[Dict[str, Any]] = []
    
    i = 0
    chunk_idx = 0
    n = len(sent_with_page)
    
    while i < n:
        current_sents: List[str] = []
        pages_in_chunk: List[int] = []
        
        length_acc = 0
        j = i
        while j < n:
            s, p = sent_with_page[j]
            s_len = len(s)
            if s_len == 0:
                j += 1
                continue
            
            if current_sents and length_acc + s_len > chunk_size:
                break
            
            current_sents.append(s)
            pages_in_chunk.append(p)
            length_acc += s_len
            j += 1
        
        if not current_sents:
            if j < n:
                s, p = sent_with_page[j]
                current_sents = [s]
                pages_in_chunk = [p]
                j += 1
            else:
                break
        
        chunk_text = strip_noise_scripts(" ".join(current_sents))
        chunk_pages = sorted(set(pages_in_chunk))
        
        # 최소 크기 미만인 경우 이전 청크에 병합 시도
        if len(chunk_text) < min_chunk_size and chunks:
            # 이전 청크에 병합
            prev_chunk = chunks[-1]
            prev_chunk["text"] += " " + chunk_text
            prev_chunk["page_end"] = chunk_pages[-1]
            prev_chunk["sentence_count"] += len(current_sents)
            logger.debug(f"짧은 청크를 이전 청크에 병합: {len(chunk_text)}자")
        else:
            chunk_obj = {
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "page_start": chunk_pages[0],
                "page_end": chunk_pages[-1],
                "locator_type": locator_type,
                "sentence_count": len(current_sents),
            }
            chunks.append(chunk_obj)
            chunk_idx += 1
        
        if overlap_sents > 0:
            i = max(j - overlap_sents, i + 1)
        else:
            i = j
    
    # 최종 필터링: 최소 크기 미만 또는 양식 템플릿 청크 제거
    filtered_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) < min_chunk_size:
            logger.info(f"최소 크기 미만 청크 제거: {len(chunk['text'])}자")
        elif _is_form_template_chunk(chunk["text"]):
            logger.info(f"양식 템플릿 청크 제거: chunk_index={chunk['chunk_index']}")
        else:
            filtered_chunks.append(chunk)

    # 청크 인덱스 재정렬
    for idx, chunk in enumerate(filtered_chunks):
        chunk["chunk_index"] = idx

    return filtered_chunks


def chunk_by_rows_with_meta(
    rows_with_meta: List[Tuple[str, int, str]],
    chunk_size: int = 800,
    overlap_rows: int = 1,
    min_chunk_size: int = 100  # 최소 청크 크기 (문자 수)
) -> List[Dict[str, Any]]:
    """엑셀/CSV 행 기반 청킹"""
    chunks: List[Dict[str, Any]] = []
    i = 0
    chunk_idx = 0
    n = len(rows_with_meta)
    
    while i < n:
        current_rows: List[str] = []
        sheets: List[str] = []
        row_ids: List[int] = []
        length_acc = 0
        
        j = i
        while j < n:
            sheet_name, row_idx, text = rows_with_meta[j]
            t_len = len(text)
            if t_len == 0:
                j += 1
                continue
            
            if current_rows and length_acc + t_len > chunk_size:
                break
            
            current_rows.append(text)
            sheets.append(sheet_name)
            row_ids.append(row_idx)
            length_acc += t_len
            j += 1
        
        if not current_rows:
            if j < n:
                sheet_name, row_idx, text = rows_with_meta[j]
                current_rows = [text]
                sheets = [sheet_name]
                row_ids = [row_idx]
                j += 1
            else:
                break
        
        chunk_text = strip_noise_scripts("\n".join(current_rows))
        sheet_unique = sorted(set(sheets))
        
        # 최소 크기 미만인 경우 이전 청크에 병합 시도
        if len(chunk_text) < min_chunk_size and chunks:
            prev_chunk = chunks[-1]
            prev_chunk["text"] += "\n" + chunk_text
            prev_chunk["sheet_end"] = sheet_unique[-1]
            prev_chunk["row_end"] = max(row_ids) if row_ids else prev_chunk.get("row_end")
            prev_chunk["row_count"] += len(current_rows)
            logger.debug(f"짧은 청크를 이전 청크에 병합: {len(chunk_text)}자")
        else:
            chunk_obj = {
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "sheet_start": sheet_unique[0],
                "sheet_end": sheet_unique[-1],
                "row_start": min(row_ids) if row_ids else None,
                "row_end": max(row_ids) if row_ids else None,
                "row_count": len(current_rows),
            }
            chunks.append(chunk_obj)
            chunk_idx += 1
        
        if overlap_rows > 0:
            i = max(j - overlap_rows, i + 1)
        else:
            i = j
    
    # 최종 필터링: 최소 크기 미만 또는 양식 템플릿 청크 제거
    filtered_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) < min_chunk_size:
            logger.debug(f"최소 크기 미만 청크 제거: {len(chunk['text'])}자")
        elif _is_form_template_chunk(chunk["text"]):
            logger.info(f"양식 템플릿 청크 제거: chunk_index={chunk['chunk_index']}")
        else:
            filtered_chunks.append(chunk)

    # 청크 인덱스 재정렬
    for idx, chunk in enumerate(filtered_chunks):
        chunk["chunk_index"] = idx

    return filtered_chunks


def chunk_by_sentences_with_page_estimated(
    pages: List[Tuple[int, str]],
    locator_type: str = "page_estimated",
    chunk_size: int = 800,
    overlap_sents: int = 2,
    min_chunk_size: int = 100
) -> List[Dict[str, Any]]:
    """페이지 + 문장 기반 청킹 (페이지 추정 정보 포함, 대표 페이지 기반)
    
    Args:
        pages: [(page_no_or_section, text), ...] 리스트
        locator_type: "page" (실제 페이지) 또는 "page_estimated" (추정 페이지) 또는 "section"
        chunk_size: 청크 크기 (문자 수)
        overlap_sents: 오버랩 문장 수
        min_chunk_size: 최소 청크 크기 (문자 수)
    
    Returns:
        청크 목록 (locator_type, page_confidence, page_source 포함)
        - locator_type="section"인 경우: page_start/page_end는 None
        - locator_type="page_estimated"인 경우: 대표 페이지(mode 또는 median) 기반
    """
    from statistics import mode, median
    
    sent_with_page = build_sentence_list_with_page(pages)
    chunks: List[Dict[str, Any]] = []
    
    i = 0
    chunk_idx = 0
    n = len(sent_with_page)
    
    while i < n:
        current_sents: List[str] = []
        pages_in_chunk: List[int] = []
        
        length_acc = 0
        j = i
        while j < n:
            s, p = sent_with_page[j]
            s_len = len(s)
            if s_len == 0:
                j += 1
                continue
            
            if current_sents and length_acc + s_len > chunk_size:
                break
            
            current_sents.append(s)
            pages_in_chunk.append(p)
            length_acc += s_len
            j += 1
        
        if not current_sents:
            if j < n:
                s, p = sent_with_page[j]
                current_sents = [s]
                pages_in_chunk = [p]
                j += 1
            else:
                break
        
        chunk_text = strip_noise_scripts(" ".join(current_sents))

        # locator_type에 따라 page 처리
        if locator_type == "section":
            # section fallback: page_start/page_end는 None
            page_start = None
            page_end = None
            section_index = pages_in_chunk[0] if pages_in_chunk else None
        else:
            # page_estimated: 대표 페이지 계산 (mode 우선, 실패 시 median)
            try:
                representative_page = mode(pages_in_chunk)
            except:
                representative_page = int(median(pages_in_chunk))
            page_start = representative_page
            page_end = representative_page
            section_index = None
        
        # 최소 크기 미만인 경우 이전 청크에 병합 시도
        if len(chunk_text) < min_chunk_size and chunks:
            prev_chunk = chunks[-1]
            prev_chunk["text"] += " " + chunk_text
            prev_chunk["sentence_count"] += len(current_sents)
            logger.debug(f"짧은 청크를 이전 청크에 병합: {len(chunk_text)}자")
        else:
            chunk_obj = {
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "page_start": page_start,
                "page_end": page_end,
                "locator_type": locator_type,
                "page_confidence": 0.7 if locator_type == "page_estimated" else None,
                "page_source": "footer_anchor" if locator_type == "page_estimated" else None,
                "sentence_count": len(current_sents),
            }
            
            # section fallback인 경우 section_index 추가
            if locator_type == "section" and section_index is not None:
                chunk_obj["section_index"] = section_index
            
            chunks.append(chunk_obj)
            chunk_idx += 1
        
        if overlap_sents > 0:
            i = max(j - overlap_sents, i + 1)
        else:
            i = j
    
    # 최종 필터링: 최소 크기 미만 또는 양식 템플릿 청크 제거
    filtered_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) < min_chunk_size:
            logger.info(f"최소 크기 미만 청크 제거: {len(chunk['text'])}자")
        elif _is_form_template_chunk(chunk["text"]):
            logger.info(f"양식 템플릿 청크 제거: chunk_index={chunk['chunk_index']}")
        else:
            filtered_chunks.append(chunk)
    
    # 청크 인덱스 재정렬
    for idx, chunk in enumerate(filtered_chunks):
        chunk["chunk_index"] = idx
    
    logger.info(f"청킹 완료 (locator_type={locator_type}): {len(filtered_chunks)}개 청크")
    
    return filtered_chunks

