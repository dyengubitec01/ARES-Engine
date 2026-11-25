"""파일 형식별 텍스트 추출기"""
import logging
import csv
import re
import os
import subprocess
import tempfile
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import fitz  # PyMuPDF
import docx
from openpyxl import load_workbook
import xlrd
from pptx import Presentation

from .quality_score import score_chunk_corruption

logger = logging.getLogger(__name__)


@dataclass
class PageAnchor:
    """페이지 번호 anchor 정보"""
    para_idx: int  # 문단 인덱스
    page_no: int  # 페이지 번호
    confidence: float  # 신뢰도 (0.0~1.0)
    source: str  # 출처 (footer_anchor, header_anchor, interpolation, fallback)


@dataclass
class HwpxParagraph:
    """HWPX 문단 정보"""
    para_idx: int  # 문단 인덱스
    text: str  # 텍스트
    section_idx: int  # 섹션 인덱스
    relative_position: float  # 섹션 내 상대 위치 (0.0~1.0)

# gethwp는 optional dependency (HWP/HWPX 지원, 페이지 정보 없음)
try:
    import gethwp
except ImportError:
    gethwp = None
    logger.warning("gethwp 모듈을 찾을 수 없습니다. HWP/HWPX 파일 처리가 비활성화됩니다.")

# pdfplumber는 optional dependency (PDF CMap 해석 개선, HWP→PDF 변환 문서에 효과적)
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None
    PDFPLUMBER_AVAILABLE = False
    logger.info("pdfplumber 미설치. PDF 추출 시 PyMuPDF만 사용합니다.")

# pyhwpx는 더 이상 사용하지 않음 (하위 호환성을 위해 변수만 유지)
PYHWPX_AVAILABLE = False

# PDF 사전검사: 도면/이미지 PDF 차단용 임계값
# CAD에서 출력된 벡터 도면 PDF는 텍스트도 풍부해 길이만으로는 못 거른다.
# 그래서 벡터 객체(lines+curves)의 페이지당 평균까지 본다.
# 일반 문서: 페이지당 수십~수백, 도면 PDF: 페이지당 수만~수십만.
_PDF_PRECHECK_SAMPLE_SIZE = 8
_PDF_PRECHECK_MIN_TEXT_LEN = 500
_PDF_PRECHECK_MIN_AVG_PER_PAGE = 100
_PDF_PRECHECK_MIN_BODY_AVG = 80
_PDF_PRECHECK_MAX_VECTOR_OBJS_PER_PAGE = 5000

# XLSX 추출 안전장치: 빈 행 무한 순회·청크 폭증·hidden 시트 노이즈 차단
# 엑셀의 max_row가 1,048,576로 잡힌 시트(셀 서식 잔재 등)도 안전하게 끊는다.
_XLSX_SKIP_HIDDEN_SHEETS = True       # 숨김/매우숨김 시트는 추출 대상에서 제외
_XLSX_BLANK_ROW_TERMINATE = 100       # 연속 빈 행이 이만큼 나오면 시트 종료
_XLSX_MAX_ROWS_PER_SHEET = 50000      # 시트당 추출 행 상한 (안전망)
_XLSX_MAX_TOTAL_ROWS = 100000         # 한 파일 전체 추출 행 상한 (안전망)


def _remove_garbled_cjk(text: str) -> str:
    """HWP gethwp 폴백에서 발생하는 깨진 CJK 문자 제거.
    
    gethwp가 HWP 바이너리 섹션을 잘못 디코딩하면 CJK 통일 한자(U+4E00~U+9FFF) 범위의
    깨진 문자가 섞여 나옴. 한국어 HWP 문서에서는 이런 범위의 한자가 정상 콘텐츠일
    가능성이 낮으므로 공백으로 대체.
    """
    if not text:
        return text
    # CJK Unified Ideographs 및 Extension A/B 블록 제거
    # U+3400-U+9FFF: CJK Extension A, Unified Ideographs
    # U+F900-U+FAFF: CJK Compatibility Ideographs
    cleaned = re.sub(r'[\u3400-\u9FFF\uF900-\uFAFF]+', ' ', text)
    # 연속 공백 정리
    cleaned = re.sub(r'  +', ' ', cleaned)
    return cleaned.strip()


def _strip_null_chars(text: str) -> str:
    """제어 문자 제거 (C0 + C1 영역).

    제거 대상:
    - C0 제어문자 \x00~\x08, \x0B~\x0C, \x0E~\x1F
    - C1 제어문자 \x80~\x9F (APPLICATION PROGRAM COMMAND 등 - PDF/HWP 추출 시 빈번)

    유지:
    - \x09: Tab
    - \x0A: 줄바꿈 (LF)
    - \x0D: 캐리지 리턴 (CR)
    """
    if not text:
        return text

    import re
    # C0 제어 (Tab, LF, CR 제외) + C1 제어 전체
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x80-\x9F]', '', text)

    return text


def _clean_common_noise(text: str) -> str:
    """모든 파일 타입 공통 노이즈 제거.

    - PUA(Private Use Area) 문자: 폰트 매핑된 의미 없는 불릿/기호
    - SHY(소프트 하이픈, U+00AD): 보이지 않는 하이픈
    - ZWSP/ZWNJ/ZWJ 등 제로폭 문자
    - HTML 엔티티 (&nbsp; 등)
    - PDF CID 참조 ((cid:XXXXX))
    - 인코딩 깨짐으로 발생하는 Latin Extended 불릿 문자 (Ÿ, ž 등)
    - Unicode Replacement Character (U+FFFD, �)
    - White Square (U+25A1, □) — 폰트 미지원/인코딩 깨짐
    - UTF-8 mojibake 패턴 (ï¿½)
    - 인라인 이미지 OLE 메타 텍스트 (여러 속성이 이어진 경우 포함)
    - HWPX 필드코드 머리글/꼬리글 (^1. ^2. 등)
    - HWPX 하이퍼링크/북마크 메타데이터
    """
    import html as html_module

    if not text:
        return text

    # 제어 문자 제거 (안전장치: _strip_null_chars 누락 경로 대비)
    # C0: \x00-\x08, \x0B-\x0C, \x0E-\x1F (Tab/LF/CR 예외)
    # C1: \x80-\x9F (PDF/HWP 추출에서 빈번한 누락 영역)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x80-\x9F]', '', text)

    # HTML 엔티티 디코딩 (&nbsp; &amp; &lt; 등)
    text = html_module.unescape(text)

    # NBSP 및 전각 공백 → 일반 공백 (html.unescape 후 \xa0이 남을 수 있음)
    text = text.replace('\u00a0', ' ')
    text = text.replace('\u3000', ' ')

    # PUA 문자 제거
    # BMP PUA (U+E000~U+F8FF)
    # Supplementary PUA-A (U+F0000~U+FFFFF)
    # Supplementary PUA-B (U+100000~U+10FFFF)
    text = re.sub(r'[\uE000-\uF8FF\U000F0000-\U000FFFFF\U00100000-\U0010FFFF]', '', text)

    # SHY (소프트 하이픈) 제거
    text = text.replace('\u00ad', '')

    # 제로폭 문자 제거 (ZWSP, ZWNJ, ZWJ, WJ, FEFF BOM)
    text = re.sub(r'[\u200B-\u200D\u2060\uFEFF]', '', text)

    # PDF CID 참조 제거: (cid:12345) 패턴
    text = re.sub(r'\(cid:\d+\)', '', text)

    # 인코딩 깨짐 Latin Extended 문자 제거
    # Ÿ(U+0178), ž(U+017E) 등이 불릿/기호로 오용되는 경우
    # Latin Extended-A/B 범위에서 한국어 문서에 정상적으로 등장하지 않는 문자
    text = re.sub(r'[\u0152-\u0178]', '', text)

    # Unicode Replacement Character (U+FFFD) 제거
    # 인코딩 변환 실패 시 삽입되는 대체 문자
    text = text.replace('\uFFFD', '')

    # White Square (□, U+25A1) 제거
    # 폰트 미지원/인코딩 깨짐으로 발생하는 네모 기호
    text = text.replace('\u25A1', '')

    # UTF-8 mojibake 패턴 (ï¿½) 제거
    # U+FFFD의 UTF-8 바이트(EF BF BD)가 Latin-1로 잘못 디코딩된 결과
    text = text.replace('ï¿½', '')

    # Specials 블록 잔여 처리 (U+FFF0~U+FFFF, U+FFFD 제외)
    # U+FFF0~U+FFF8: Reserved / U+FFF9~U+FFFB: Interlinear annotation
    # U+FFFC: Object replacement / U+FFFE~U+FFFF: Noncharacter (정상 등장 불가)
    text = re.sub(r'[￰-￼￾￿]', '', text)

    # 인라인 이미지 OLE 메타 텍스트 제거
    # "그림입니다. 원본 그림의 이름: CLP00002c7c0001. bmp 원본 그림의 크기: 가로 1011pixel, 세로 793pixel" 등
    # "그림입니다." 부터 300자 이내의 마지막 이미지 관련 키워드(pixel, bmp 등)까지 통째로 제거
    text = re.sub(
        r'그림입니다\..{0,300}(?:pixel|bmp|jpg|jpeg|png|gif|tif|tiff|emf|wmf)\b[,\s]*',
        '', text, flags=re.IGNORECASE
    )

    # HWPX 필드코드 머리글/꼬리글 제거
    # "^1. ^2. ^3) ^4) (^5) (^6) ^7" 등이 텍스트 앞에 붙는 패턴
    text = re.sub(r'^(?:\s*\(?\^[\d]+[.)]*\)?\s*)+', '', text)

    # HWPX 하이퍼링크/북마크 메타데이터 제거
    text = re.sub(r'TARGET_BOOKMARK\b', '', text)
    text = re.sub(r'OBJECT_TYPE_PAGE\b', '', text)
    text = re.sub(r'HWPHYPERLINK_JUMP_\w+', '', text)

    # HWPX 북마크 참조 패턴 제거: "? Ⅰ. 제목;6;0;0;0;" → "Ⅰ. 제목"
    text = re.sub(r'\?\s*([^;]+);\d+;\d+;\d+;\d+;', r'\1', text)

    # 반복 구분선/장식 문자 제거 (3개 이상 반복)
    # 중간점(·‧・), 마침표(.), 하이픈(-), 등호(=), 물결(~), 언더스코어(_),
    # 별표(*), 샵(#), 한글 으(ㅡ), 기하 기호(◆■□○●▶▷◇◈★☆)
    text = re.sub(r'[·‧・′\'\.\…\-=~_*#ㅡ◆■□○●▶▷◇◈★☆]{5,}', ' ', text)

    # 정리 후 연속 공백 재정리
    text = re.sub(r' {2,}', ' ', text)

    return text


def _remove_pdf_hyphens(text: str) -> str:
    """PDF 줄바꿈 하이픈 제거 (단어 복원)

    PDF에서 줄바꿈으로 인해 생긴 하이픈을 제거하여 원래 단어를 복원합니다.
    예: "계약-\\n서" → "계약서"
    """
    if not text:
        return text

    # "-\n" 패턴 제거 (하이픈 + 줄바꿈)
    text = text.replace("-\n", "")

    # "-\r\n" 패턴도 제거 (Windows 줄바꿈)
    text = text.replace("-\r\n", "")

    return text


def _postprocess_pdf_text(text: str) -> str:
    """PDF 추출 텍스트 후처리 (공백 정규화, 구두점 정리)

    HWP→PDF 변환 등에서 발생하는 공백/구두점 문제를 보정합니다.
    """
    if not text:
        return text

    # 1. NBSP 및 특수 공백 → 일반 공백
    text = text.replace('\u00a0', ' ')
    text = text.replace('\u3000', ' ')

    # 2. 연속 공백 정리
    text = re.sub(r' {2,}', ' ', text)

    # 3. 구두점 앞 불필요한 공백 제거: "있는 , 도시" → "있는, 도시"
    text = re.sub(r'\s+([,.)!?;:\]」\)])', r'\1', text)

    # 4. 여는 괄호·인용부호 뒤 불필요한 공백 제거: "( 스마트" → "(스마트"
    text = re.sub(r'([(\[「\(])\s+', r'\1', text)

    # 5. 정리 후 발생한 연속 공백 재정리
    text = re.sub(r' {2,}', ' ', text)

    return text


def _join_korean_line_breaks(text: str) -> str:
    """PDF 레이아웃 줄바꿈으로 인한 한국어 단어 분리 복원.

    PDF는 시각적 줄 너비에 맞춰 텍스트를 줄바꿈하므로 한국어 단어가
    줄 경계에서 분리됨. 예: "신기\\n술을" → "신기술을"

    판단 기준:
    - 줄 길이가 중간값의 75% 이상이면 '줄바꿈 래핑'으로 간주
    - 줄 끝 한글 + 다음 줄 시작 한글 + 문장 종결 아님 → 단어 분리로 판단
    """
    if not text:
        return text

    lines = text.split('\n')
    if len(lines) < 3:
        return text

    # 줄 길이 중간값 계산 (full-width 판단 기준)
    line_lengths = [len(line.rstrip()) for line in lines if line.strip()]
    if not line_lengths:
        return text
    line_lengths_sorted = sorted(line_lengths)
    median_len = line_lengths_sorted[len(line_lengths_sorted) // 2]
    threshold = median_len * 0.75

    result = []
    for i, line in enumerate(lines):
        result.append(line)
        if i < len(lines) - 1:
            stripped = line.rstrip()
            next_stripped = lines[i + 1].lstrip()

            is_full_width = len(stripped) >= threshold
            ends_korean = stripped and '\uAC00' <= stripped[-1] <= '\uD7A3'
            starts_korean = next_stripped and '\uAC00' <= next_stripped[0] <= '\uD7A3'
            not_sentence_end = not re.search(r'[.!?。:;]\s*$', stripped)

            if is_full_width and ends_korean and starts_korean and not_sentence_end:
                pass  # 줄바꿈 없이 연결 (단어 분리 복원)
            else:
                result.append('\n')

    return ''.join(result)


def _normalize_unicode(text: str) -> str:
    """유니코드 정규화 (NFC)
    
    한글 등의 문자를 NFC 형식으로 통일하여 일관성을 확보합니다.
    예: NFD "한글" → NFC "한글" (같은 글자, 다른 코드)
    """
    if not text:
        return text
    
    import unicodedata
    return unicodedata.normalize('NFC', text)


def _is_formula_or_noise(text: str) -> bool:
    """수식이나 노이즈 텍스트 판별
    
    엑셀 수식, 특수 패턴, 의미없는 문자열 필터링
    """
    if not text or (len(text) < 2 and not text.isdigit()):
        return True
    
    # 엑셀 수식 패턴
    if text.startswith('=') or '=SUM(' in text or '=AVERAGE(' in text or '=COUNT(' in text:
        return True
    
    # 특수 패턴 (노이즈)
    noise_patterns = [
        r'%g,;+',  # %g,;; 같은 패턴
        r'^[?]+$',  # ??? 같은 패턴
        r'^\W+$',  # 특수문자만 있는 경우 (단, 2자 이상)
    ]
    for pattern in noise_patterns:
        if re.search(pattern, text):
            return True

    # 양식 템플릿 패턴: 한글 1글자 + 공백 2개 이상 반복 ("대   표   자", "주        소")
    if re.match(r'^[\uAC00-\uD7A3](\s{2,}[\uAC00-\uD7A3])+\s*$', text.strip()):
        return True

    # 빈 날짜 양식: "2024.     .     ."
    if re.match(r'^\d{4}\.\s{2,}\.\s{2,}\.\s*$', text.strip()):
        return True

    # 양식 직인 자리: "(인)" 단독
    if text.strip() == '(인)':
        return True

    # HWPX 필드코드 노이즈: "^1." "^2)" "(^5)" 등이 반복되는 패턴
    if '^' in text and re.match(r'^[\s\^()\d.\-:)]+$', text):
        return True

    # HWPX 이미지 OLE 메타 텍스트
    if '그림입니다.' in text and ('원본 그림의' in text or 'image' in text.lower()):
        return True

    # 이미지 메타 패턴: "원본 그림의 이름:", "원본 그림의 크기:" 등
    if re.search(r'원본 그림의\s*(이름|크기|종류)', text):
        return True

    # HWPX 하이퍼링크 메타데이터만으로 구성된 텍스트
    if 'TARGET_BOOKMARK' in text or 'HWPHYPERLINK_JUMP_' in text or 'OBJECT_TYPE_PAGE' in text:
        # 메타데이터 키워드를 제거했을 때 의미 있는 텍스트가 남지 않으면 노이즈
        stripped = re.sub(r'TARGET_BOOKMARK|OBJECT_TYPE_PAGE|HWPHYPERLINK_JUMP_\w+|true|false', '', text, flags=re.IGNORECASE)
        stripped = re.sub(r'[;\d\s?]+', '', stripped)
        if len(stripped.strip()) < 5:
            return True

    # CID 참조만으로 구성된 텍스트
    if '(cid:' in text:
        stripped = re.sub(r'\(cid:\d+\)', '', text).strip()
        if not stripped:
            return True

    return False


def _is_inside_table(elem) -> bool:
    """요소가 표 내부에 있는지 확인 (deprecated, _is_elem_inside_table 사용)"""
    parent = elem
    max_depth = 20  # 무한 루프 방지
    depth = 0
    
    while parent is not None and depth < max_depth:
        tag_name = parent.tag.split('}')[-1] if '}' in parent.tag else parent.tag
        if tag_name.lower() in ['tbl', 'table', 'tr', 'tc', 'cell']:
            return True
        # XML 요소의 부모 찾기 (ElementTree는 _parent 속성이 없을 수 있음)
        parent = getattr(parent, '_parent', None)
        depth += 1
    
    return False


def _is_elem_inside_table(elem, processed_tables: set) -> bool:
    """요소가 이미 처리된 표 내부에 있는지 확인
    
    Args:
        elem: 확인할 XML 요소
        processed_tables: 이미 처리한 표 요소의 id() 집합
    """
    # 부모를 따라 올라가며 표 요소 확인
    parent = elem
    max_depth = 50
    depth = 0
    
    while parent is not None and depth < max_depth:
        # 이미 처리한 표인지 확인
        if id(parent) in processed_tables:
            return True
        
        # 표 태그인지 확인
        tag_name = parent.tag.split('}')[-1] if '}' in parent.tag else parent.tag
        if tag_name.lower() in ['tbl', 'table']:
            return True
        
        # 부모로 이동 (ElementTree는 부모 참조가 없으므로 중단)
        parent = getattr(parent, '_parent', None)
        depth += 1
    
    return False


def _extract_hwpx_table(table_elem) -> str:
    """HWPX 표 요소에서 구조화된 텍스트 추출
    
    표의 각 행을 구분하고, 셀은 | 로 구분하여 의미있는 텍스트로 변환
    """
    rows_text = []
    
    # 표의 모든 행(tr) 찾기
    for row_elem in table_elem.iter():
        tag_name = row_elem.tag.split('}')[-1] if '}' in row_elem.tag else row_elem.tag
        
        if tag_name.lower() in ['tr', 'row']:
            cells_text = []
            
            # 행의 모든 셀(tc/cell) 찾기
            for cell_elem in row_elem.iter():
                cell_tag = cell_elem.tag.split('}')[-1] if '}' in cell_elem.tag else cell_elem.tag
                
                if cell_tag.lower() in ['tc', 'cell']:
                    # 셀 내부의 모든 텍스트 수집
                    cell_texts = []
                    for text_elem in cell_elem.iter():
                        if text_elem.text:
                            text = _normalize_unicode(_strip_null_chars(text_elem.text)).strip()
                            if text and not _is_formula_or_noise(text):
                                cell_texts.append(text)
                    
                    if cell_texts:
                        cells_text.append(' '.join(cell_texts))
            
            # 행에 데이터가 있으면 추가
            if cells_text:
                rows_text.append(' | '.join(cells_text))
    
    return '\n'.join(rows_text) if rows_text else ''


def _extract_hwpx_content(root) -> str:
    """HWPX XML 루트에서 모든 콘텐츠 추출 (표와 일반 텍스트 구분)
    
    표는 구조화하여 추출하고, 일반 텍스트는 순서대로 추출
    """
    from xml.etree import ElementTree as ET
    
    content_parts = []
    
    # 재귀적으로 요소를 순회하며 표와 텍스트 추출
    def process_element(elem, inside_table=False):
        tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        
        # 표 요소 발견
        if tag_name.lower() in ['tbl', 'table']:
            table_text = _extract_hwpx_table_structured(elem)
            if table_text:
                content_parts.append(table_text)
            return  # 표 내부는 더 이상 처리하지 않음
        
        # 표 내부가 아닌 경우 텍스트 추출
        if not inside_table and elem.text:
            text = _normalize_unicode(_strip_null_chars(elem.text)).strip()
            if text and not _is_formula_or_noise(text):
                content_parts.append(text)
        
        # 자식 요소 처리
        for child in elem:
            process_element(child, inside_table=inside_table or tag_name.lower() in ['tbl', 'table'])
    
    process_element(root)
    
    return '\n'.join(content_parts)


def _extract_hwpx_table_structured(table_elem) -> str:
    """HWPX 표를 구조화된 텍스트로 변환
    
    각 행을 줄바꿈으로 구분하고, 셀은 | 로 구분
    """
    rows_data = []
    
    # 직접 자식 요소 중 행(tr) 찾기
    for child in table_elem:
        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        if tag_name.lower() in ['tr', 'row']:
            cells = []
            
            # 행의 자식 요소 중 셀(tc) 찾기
            for cell_elem in child:
                cell_tag = cell_elem.tag.split('}')[-1] if '}' in cell_elem.tag else cell_elem.tag
                
                if cell_tag.lower() in ['tc', 'cell']:
                    # 셀의 모든 텍스트 수집
                    cell_text = _extract_all_text(cell_elem)
                    if cell_text:
                        cells.append(cell_text)
            
            if cells:
                rows_data.append(' | '.join(cells))
    
    return '\n'.join(rows_data) if rows_data else ''


def _extract_all_text(elem) -> str:
    """XML 요소의 모든 텍스트를 재귀적으로 추출"""
    texts = []
    
    if elem.text:
        text = _normalize_unicode(_strip_null_chars(elem.text)).strip()
        if text and not _is_formula_or_noise(text):
            texts.append(text)
    
    for child in elem:
        child_text = _extract_all_text(child)
        if child_text:
            texts.append(child_text)
        
        # tail 텍스트도 포함
        if child.tail:
            tail = _normalize_unicode(_strip_null_chars(child.tail)).strip()
            if tail and not _is_formula_or_noise(tail):
                texts.append(tail)
    
    return ' '.join(texts)


def _is_page_number_pattern(text: str, para: Optional[HwpxParagraph] = None, prev_page_no: Optional[int] = None, next_page_no: Optional[int] = None) -> bool:
    """페이지 번호 패턴인지 확인 (보수적)
    
    인식 패턴:
    - "- 12 -" (강한 패턴)
    - "12 / 230" (강한 패턴)
    - "Page 12" (강한 패턴)
    - "12쪽", "12페이지" (강한 패턴)
    - 숫자만 있는 문단 ("12"): 3개 이상 조건 충족 시만 허용
    """
    if not text or len(text) > 30:
        return False
    
    text = text.strip()
    
    # 강한 패턴들 (조건 없이 허용)
    # 패턴 1: "- 12 -" (공백 허용)
    if re.match(r'^\s*-\s*(\d{1,4})\s*-\s*$', text):
        return True
    
    # 패턴 2: "12 / 230" (공백 허용)
    if re.match(r'^\s*(\d{1,4})\s*/\s*\d{1,4}\s*$', text):
        return True
    
    # 패턴 3: "Page 12" (공백 허용, 대소문자 무관)
    if re.match(r'^\s*page\s*(\d{1,4})\s*$', text, re.IGNORECASE):
        return True
    
    # 패턴 4: "12쪽", "12페이지" (공백 허용)
    if re.match(r'^\s*(\d{1,4})\s*(쪽|페이지)\s*$', text):
        return True
    
    # 단독 숫자 패턴: 매우 보수적으로 처리
    if re.match(r'^\d+$', text):
        if para is None:
            return False  # 문단 정보 없으면 거부
        
        # 조건 체크
        conditions_met = 0
        
        # 조건 1: 문단 길이 매우 짧음 (3자 이하)
        if len(text) <= 3:
            conditions_met += 1
        
        # 조건 2: section 내 상단 5% 또는 하단 5% 위치
        if para.relative_position <= 0.05 or para.relative_position >= 0.95:
            conditions_met += 1
        
        # 조건 3: 이전 또는 다음 anchor와 +1 연속성
        try:
            current_no = int(text)
            if prev_page_no is not None and current_no == prev_page_no + 1:
                conditions_met += 1
            elif next_page_no is not None and current_no == next_page_no - 1:
                conditions_met += 1
        except ValueError:
            pass
        
        # 3개 이상 조건 충족 시만 허용
        return conditions_met >= 3
    
    return False


def _is_excluded_pattern(text: str) -> bool:
    """페이지 번호 후보에서 제외할 패턴인지 확인 (보수적)
    
    제외 패턴:
    - "1. 제목", "1.1 제목"
    - "표 3-1", "그림 2"
    - 목차 점선 패턴
    - 긴 문장 속 숫자
    - 통계 수치 나열 문단
    - 숫자 토큰 3개 이상
    - 쉼표 포함 숫자 2개 이상
    """
    if not text:
        return True
    
    text = text.strip()
    
    # 제목 패턴: "1. 제목", "1.1 제목"
    if re.match(r'^\d+(\.\d+)*\s+\S+', text):
        return True
    
    # 표/그림 패턴: "표 3-1", "그림 2"
    if re.match(r'^(표|그림|Table|Figure|도표|차트)\s+\d+', text, re.IGNORECASE):
        return True
    
    # 목차 점선 패턴: "....... 12"
    if '...' in text or '․․․' in text:
        return True
    
    # 긴 문장 (30자 이상)
    if len(text) > 30:
        return True
    
    # 숫자 토큰이 3개 이상 포함된 문단
    number_tokens = re.findall(r'\d+', text)
    if len(number_tokens) >= 3:
        return True
    
    # 쉼표 포함 숫자가 2개 이상인 문단 (통계 수치)
    # 예: "25,104", "49,520"
    comma_numbers = re.findall(r'\d{1,3}(?:,\d{3})+', text)
    if len(comma_numbers) >= 2:
        return True
    
    # 연도 패턴이 포함된 문단 (통계 문단 가능성)
    # 예: "2019년", "2023년"
    if re.search(r'(19|20)\d{2}년', text):
        return True
    
    return False


def _calculate_plausible_max_page(paragraphs: List[HwpxParagraph]) -> int:
    """문서 길이 기반 plausible max page 계산
    
    Args:
        paragraphs: 문단 목록
    
    Returns:
        합리적인 최대 페이지 번호
    """
    if not paragraphs:
        return 30
    
    # 총 토큰 수 추정 (한글 기준 평균 2자 = 1토큰)
    total_chars = sum(len(p.text) for p in paragraphs)
    estimated_tokens = total_chars // 2
    
    # 페이지당 평균 250토큰 가정
    max_page_by_tokens = max(30, estimated_tokens // 250)
    
    # 문단 수 기반 (페이지당 평균 10문단 가정)
    max_page_by_paras = max(30, len(paragraphs) // 10)
    
    # 두 값 중 큰 값 사용 (보수적)
    plausible_max = max(max_page_by_tokens, max_page_by_paras)
    
    # 상한선: 1000페이지
    return min(plausible_max, 1000)


def _calculate_page_candidate_score(
    para: HwpxParagraph,
    prev_page_no: Optional[int],
    total_paras: int,
    max_plausible_page: int
) -> float:
    """페이지 번호 후보의 점수 계산
    
    점수 기준:
    - 문단 길이 12자 이하: +0.2
    - 페이지 번호 패턴 매칭: +0.4
    - 섹션 내 상대 위치가 상단 5% 또는 하단 5%: +0.2
    - 이전 확정 페이지보다 +1 증가: +0.3
    - 제외 패턴 매칭: -1.0 (제외)
    - plausible max page 초과: -1.0 (제외)
    """
    text = para.text.strip()
    score = 0.0
    
    # 제외 패턴 확인
    if _is_excluded_pattern(text):
        return -1.0
    
    # 페이지 번호 패턴 (단독 숫자는 보수적으로 처리)
    if not _is_page_number_pattern(text, para, prev_page_no):
        return -1.0
    
    # 페이지 번호 추출 및 plausible 검증
    page_no = _extract_page_number(text)
    if page_no is None or page_no < 1 or page_no > max_plausible_page:
        return -1.0
    
    # 문단 길이
    if len(text) <= 12:
        score += 0.2
    
    # 강한 패턴 보너스
    if re.match(r'^-\s*\d+\s*-$', text) or re.match(r'^\d+\s*/\s*\d+$', text):
        score += 0.4
    else:
        score += 0.2
    
    # 섹션 내 상대 위치 (상단 5% 또는 하단 5%)
    if para.relative_position <= 0.05 or para.relative_position >= 0.95:
        score += 0.2
    
    # 이전 페이지 번호와의 연속성 확인
    if prev_page_no is not None:
        if page_no == prev_page_no + 1:
            score += 0.3
        elif page_no == prev_page_no:
            score += 0.1
        elif page_no < prev_page_no:
            score -= 0.2
    
    return score


def _extract_page_number(text: str) -> Optional[int]:
    """텍스트에서 페이지 번호 추출"""
    if not text:
        return None
    
    # 숫자 추출
    numbers = re.findall(r'\d+', text)
    if not numbers:
        return None
    
    # 첫 번째 숫자를 페이지 번호로 간주
    try:
        return int(numbers[0])
    except ValueError:
        return None


def _validate_anchor_quality(anchors: List[PageAnchor]) -> Tuple[List[PageAnchor], Dict[str, Any]]:
    """anchor 품질 검증 및 필터링
    
    Args:
        anchors: 원본 anchor 목록
    
    Returns:
        (검증된 anchor 목록, 통계 정보)
    """
    stats = {
        "raw_count": len(anchors),
        "sequential_valid": True,
        "max_gap": 0,
        "filtered_count": 0
    }
    
    if len(anchors) < 3:
        # anchor가 3개 미만이면 품질 검증 실패
        stats["sequential_valid"] = False
        return [], stats
    
    # sequential 검증 및 비정상 증가폭 검출
    validated = []
    prev_anchor = None
    
    for anchor in anchors:
        if prev_anchor is None:
            validated.append(anchor)
            prev_anchor = anchor
            continue
        
        page_gap = anchor.page_no - prev_anchor.page_no
        
        # 역순이면 폐기
        if page_gap <= 0:
            stats["sequential_valid"] = False
            continue
        
        # 비정상적으로 큰 증가폭 (10페이지 이상 점프)
        if page_gap > 10:
            stats["max_gap"] = max(stats["max_gap"], page_gap)
            # 큰 gap은 폐기
            continue
        
        validated.append(anchor)
        prev_anchor = anchor
    
    stats["filtered_count"] = len(validated)
    
    # 최종 검증: 3개 미만이면 실패
    if len(validated) < 3:
        return [], stats
    
    return validated, stats


def _build_page_anchors(
    paragraphs: List[HwpxParagraph],
    score_threshold: float = 0.5
) -> Tuple[List[PageAnchor], Dict[str, Any]]:
    """페이지 anchor 목록 구축 (보수적)
    
    Args:
        paragraphs: 문단 목록
        score_threshold: anchor 확정 임계값
    
    Returns:
        (확정된 PageAnchor 목록, 통계 정보)
    """
    stats = {
        "raw_candidates": 0,
        "excluded_candidates": 0,
        "initial_anchors": 0,
        "final_anchors": 0,
        "plausible_max_page": 0
    }
    
    if not paragraphs:
        return [], stats
    
    # 디버그: 앞뒤 200개 문단 샘플링
    _log_paragraph_samples(paragraphs)
    
    # plausible max page 계산
    max_plausible_page = _calculate_plausible_max_page(paragraphs)
    stats["plausible_max_page"] = max_plausible_page
    
    anchors: List[PageAnchor] = []
    prev_page_no: Optional[int] = None
    
    for para in paragraphs:
        # raw candidate 체크 (패턴 매칭만)
        is_candidate = _is_page_number_pattern(para.text, para, prev_page_no)
        
        if is_candidate:
            stats["raw_candidates"] += 1
            
            # 제외 패턴 체크
            if _is_excluded_pattern(para.text):
                stats["excluded_candidates"] += 1
                continue
        else:
            # candidate가 아니면 skip
            continue
        
        # 점수 계산
        score = _calculate_page_candidate_score(para, prev_page_no, len(paragraphs), max_plausible_page)
        
        if score < score_threshold:
            continue
        
        # 페이지 번호 추출
        page_no = _extract_page_number(para.text)
        if page_no is None:
            continue
        
        # anchor 확정
        source = "footer_anchor" if para.relative_position >= 0.95 else "header_anchor"
        anchor = PageAnchor(
            para_idx=para.para_idx,
            page_no=page_no,
            confidence=min(score, 1.0),
            source=source
        )
        anchors.append(anchor)
        prev_page_no = page_no
        
        logger.debug(f"페이지 anchor 후보: para_idx={para.para_idx}, page={page_no}, score={score:.2f}, source={source}")
    
    stats["initial_anchors"] = len(anchors)
    
    # anchor 품질 검증
    validated_anchors, validation_stats = _validate_anchor_quality(anchors)
    stats.update(validation_stats)
    stats["final_anchors"] = len(validated_anchors)
    
    return validated_anchors, stats


def _log_paragraph_samples(paragraphs: List[HwpxParagraph], sample_size: int = 20):
    """디버그: 앞뒤 문단 샘플 로그 출력
    
    Args:
        paragraphs: 전체 문단 목록
        sample_size: 샘플 개수
    """
    if not paragraphs or not logger.isEnabledFor(logging.DEBUG):
        return
    
    # 앞 200개 문단
    front_paras = paragraphs[:200]
    # 뒤 200개 문단
    back_paras = paragraphs[-200:] if len(paragraphs) > 200 else []
    
    # 페이지 패턴 유사 문단 필터링
    pattern_samples = []
    
    for para in front_paras + back_paras:
        text = para.text.strip()
        
        # 페이지 패턴 유사 체크 (느슨하게)
        if len(text) <= 30 and re.search(r'\d+', text):
            pattern_samples.append((para.para_idx, text, para.relative_position))
        
        if len(pattern_samples) >= sample_size:
            break
    
    if pattern_samples:
        logger.debug("=== 페이지 패턴 유사 문단 샘플 (%d개) ===", len(pattern_samples))
        for idx, text, pos in pattern_samples[:sample_size]:
            logger.debug(f"  para[{idx}] pos={pos:.2f}: '{text}'")


def _assign_estimated_pages(
    paragraphs: List[HwpxParagraph],
    anchors: List[PageAnchor]
) -> List[Tuple[int, int, str, float, str]]:
    """anchor를 기반으로 모든 문단에 페이지 번호 할당
    
    Args:
        paragraphs: 문단 목록
        anchors: 확정된 anchor 목록
    
    Returns:
        List[(para_idx, page_no, locator_type, confidence, source)]
    """
    if not paragraphs:
        return []
    
    result: List[Tuple[int, int, str, float, str]] = []
    
    # anchor가 없으면 section fallback
    if not anchors:
        for para in paragraphs:
            result.append((para.para_idx, para.section_idx + 1, "section", 0.0, "fallback"))
        return result
    
    # anchor를 para_idx 기준으로 정렬
    sorted_anchors = sorted(anchors, key=lambda a: a.para_idx)
    
    # 각 문단에 페이지 할당
    for para in paragraphs:
        para_idx = para.para_idx
        
        # 해당 문단이 anchor인지 확인
        matching_anchor = next((a for a in sorted_anchors if a.para_idx == para_idx), None)
        if matching_anchor:
            result.append((
                para_idx,
                matching_anchor.page_no,
                "page_estimated",
                matching_anchor.confidence,
                matching_anchor.source
            ))
            continue
        
        # anchor 사이의 문단: 보간
        prev_anchor = None
        next_anchor = None
        
        for i, anchor in enumerate(sorted_anchors):
            if anchor.para_idx < para_idx:
                prev_anchor = anchor
            elif anchor.para_idx > para_idx:
                next_anchor = anchor
                break
        
        if prev_anchor and next_anchor:
            # 두 anchor 사이: 선형 보간
            total_dist = next_anchor.para_idx - prev_anchor.para_idx
            current_dist = para_idx - prev_anchor.para_idx
            ratio = current_dist / total_dist if total_dist > 0 else 0.5
            
            page_diff = next_anchor.page_no - prev_anchor.page_no
            estimated_page = prev_anchor.page_no + int(ratio * page_diff)
            
            confidence = min(prev_anchor.confidence, next_anchor.confidence) * 0.7  # 보간은 신뢰도 감소
            result.append((para_idx, estimated_page, "page_estimated", confidence, "interpolation"))
        
        elif prev_anchor:
            # 마지막 anchor 이후: 동일 페이지로 추정
            result.append((para_idx, prev_anchor.page_no, "page_estimated", prev_anchor.confidence * 0.5, "interpolation"))
        
        elif next_anchor:
            # 첫 anchor 이전: 동일 페이지로 추정
            result.append((para_idx, next_anchor.page_no, "page_estimated", next_anchor.confidence * 0.5, "interpolation"))
        
        else:
            # anchor가 없는 경우 (이론상 도달 불가)
            result.append((para_idx, para.section_idx + 1, "section", 0.0, "fallback"))
    
    return result


def _pdf_text_has_extraction_problem(pages: List[Tuple[int, str]]) -> bool:
    """PDF 추출 텍스트의 품질 문제를 감지.

    HWP→PDF 변환 시 폰트 CMap 문제로 발생하는 두 가지 증상을 탐지:
    1. 숫자 누락: 텍스트에 숫자가 거의 없음
    2. 숫자 위치 뒤섞임: 숫자가 한글과 분리되어 엉뚱한 위치에 배치됨
       (예: "4차산업혁명" → " 차산업혁명 ... 4 ")
    """
    total_text = '\n'.join(text for _, text in pages)
    korean_count = sum(1 for ch in total_text if '\uAC00' <= ch <= '\uD7A3')

    # 한국어 문서가 아니거나 텍스트가 너무 적으면 판단 불가
    if korean_count < 50 or len(total_text) < 200:
        return False

    total_digits = sum(1 for ch in total_text if ch.isdigit())

    # 케이스 1: 숫자가 거의 없음
    digit_ratio = total_digits / len(total_text) if total_text else 0
    if digit_ratio < 0.005:
        logger.warning(
            f"PDF 품질 문제 감지 (숫자 누락): 전체 {len(total_text)}자 중 "
            f"숫자 {total_digits}자 (비율: {digit_ratio:.4f})"
        )
        return True

    # 케이스 2: 숫자가 있지만 한글과 분리되어 있음 (위치 뒤섞임)
    if total_digits > 0:
        # 숫자가 한글에 붙어있는 정상 패턴: "4차", "제4차", "2030년", "1장"
        adjacent_pattern = re.findall(
            r'[\uAC00-\uD7A3]\d|\d[\uAC00-\uD7A3]', total_text
        )
        # 숫자가 공백으로 고립된 비정상 패턴: " 4 ", " 2030 "
        isolated_pattern = re.findall(
            r'(?:^|[\s,.])\d+(?:[\s,.]|$)', total_text
        )

        adjacent_count = len(adjacent_pattern)
        isolated_count = len(isolated_pattern)

        # 한글 문서에서 숫자-한글 인접이 하나도 없고 고립 숫자만 있으면 비정상
        if adjacent_count == 0 and isolated_count > 3:
            logger.warning(
                f"PDF 품질 문제 감지 (숫자 위치 뒤섞임): "
                f"숫자-한글 인접 {adjacent_count}회, 고립 숫자 {isolated_count}회"
            )
            return True

        # 고립 비율이 압도적으로 높아도 비정상
        total_digit_patterns = adjacent_count + isolated_count
        if total_digit_patterns > 5:
            isolated_ratio = isolated_count / total_digit_patterns
            if isolated_ratio > 0.9:
                logger.warning(
                    f"PDF 품질 문제 감지 (숫자 고립 비율 높음): "
                    f"인접 {adjacent_count}회, 고립 {isolated_count}회 "
                    f"(고립 비율: {isolated_ratio:.2f})"
                )
                return True

    # 케이스 3: 빈 괄호/인용부호 (내용이 누락된 특수문자)
    empty_brackets = len(re.findall(r'[「\(]\s*[」\)]', total_text))
    if empty_brackets >= 3:
        logger.warning(
            f"PDF 품질 문제 감지 (빈 괄호/인용부호): {empty_brackets}개"
        )
        return True

    return False



def _extract_pdf_page_text(page) -> str:
    """단일 PDF 페이지에서 일반 텍스트 추출 + 후처리.

    HWP→PDF 변환 시 숫자/특수문자가 별도 span으로 분리되어 PDF 내부 저장 순서대로
    읽으면 위치가 뒤섞이는 문제가 있음. get_text('dict')로 각 span의 좌표를 얻어
    y좌표(줄) → x좌표(좌→우) 순서로 직접 정렬하여 재조합.

    개선 사항:
    - span bbox 우측 좌표를 활용하여 span 간 공백 삽입 판단
    - y좌표 그룹핑 시 tolerance(3pt) 적용
    - 줄바꿈으로 인한 한국어 단어 분리 복원 (full-width line 감지)
    """
    try:
        d = page.get_text('dict')
        lines_by_y: Dict[float, List[tuple]] = {}

        for block in d['blocks']:
            if block['type'] != 0:  # 텍스트 블록만
                continue
            for line in block['lines']:
                for span in line['spans']:
                    t = span['text']
                    if not t.strip():
                        continue
                    y_raw = span['bbox'][1]
                    x_left = span['bbox'][0]
                    x_right = span['bbox'][2]

                    # y좌표 그룹핑: 기존 그룹과 tolerance(3pt) 이내면 병합
                    y_key = None
                    for existing_y in lines_by_y:
                        if abs(existing_y - y_raw) <= 3:
                            y_key = existing_y
                            break
                    if y_key is None:
                        y_key = round(y_raw, 0)
                        lines_by_y[y_key] = []
                    lines_by_y[y_key].append((x_left, x_right, t))

        # 페이지 우측 마진 추정 (줄바꿈 단어분리 판단용)
        all_x_rights = []
        for spans_list in lines_by_y.values():
            if spans_list:
                all_x_rights.append(max(s[1] for s in spans_list))
        right_margin = max(all_x_rights) if all_x_rights else 0

        # y 기준 정렬 후, 각 줄 내에서 x 기준 정렬 및 span 간 공백 판단
        sorted_ys = sorted(lines_by_y.keys())
        result_lines = []       # (line_text, is_full_width)
        for y in sorted_ys:
            spans = sorted(lines_by_y[y], key=lambda s: s[0])
            parts = []
            for j, (x_left, x_right, t) in enumerate(spans):
                if j > 0:
                    prev_x_right = spans[j - 1][1]
                    gap = x_left - prev_x_right
                    # 유의미한 간격(>5pt)이면 공백 삽입
                    if gap > 5:
                        parts.append(' ')
                parts.append(t)
            line_text = ''.join(parts)

            # 줄이 우측 마진 근처까지 차 있는지 (줄바꿈 단어분리 판단)
            last_x_right = spans[-1][1] if spans else 0
            is_full_width = right_margin > 0 and (right_margin - last_x_right) < 30
            result_lines.append((line_text, is_full_width))

        # 줄 결합: 한국어 단어가 줄바꿈으로 분리된 경우 공백 없이 연결
        text_parts = []
        for i, (line, is_full) in enumerate(result_lines):
            text_parts.append(line)
            if i < len(result_lines) - 1:
                next_line = result_lines[i + 1][0]
                # 조건: 현재 줄이 full-width + 한글로 끝남 + 다음 줄 한글로 시작
                #       + 문장 종결 부호로 끝나지 않음
                if (is_full and line
                        and re.search(r'[\uAC00-\uD7A3]$', line.rstrip())
                        and next_line
                        and re.search(r'^[\uAC00-\uD7A3]', next_line.lstrip())
                        and not re.search(r'[.!?。]\s*$', line)):
                    pass  # 공백/줄바꿈 없이 바로 연결
                else:
                    text_parts.append('\n')
        text = ''.join(text_parts)
    except Exception as e:
        logger.debug(f"PDF dict 기반 추출 실패, 기본 추출로 폴백: {e}")
        text = page.get_text("text", sort=True)

    if text:
        text = _remove_pdf_hyphens(text)
        text = _normalize_unicode(text)
        text = _strip_null_chars(text)
        text = _clean_common_noise(text)
        text = _postprocess_pdf_text(text)
    return text or ''


def _extract_pdf_pages_pdfplumber(path: str) -> List[Tuple[int, str]]:
    """pdfplumber(pdfminer.six) 기반 PDF 텍스트 추출.

    HWP→PDF 변환 문서에서 PyMuPDF보다 CMap 해석이 정확하여
    숫자·괄호·가운뎃점 등 특수문자가 올바르게 추출됨.
    """
    pages: List[Tuple[int, str]] = []
    try:
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            logger.info("PDF 추출 시작 (pdfplumber): %s (%d페이지)", path, total_pages)

            # 사전 검사: 분산 샘플링(앞/중/뒤) + 합계·전체평균·후반평균 세 조건
            # 표지/목차에 텍스트 풍부해도 본문(도면) 페이지가 샘플에 들어와 후반평균이 떨어짐
            if total_pages >= _PDF_PRECHECK_SAMPLE_SIZE:
                front = list(range(4))
                mid = [total_pages // 2]
                back = list(range(max(4, total_pages - 3), total_pages))
                indices = sorted(set(front + mid + back))[:_PDF_PRECHECK_SAMPLE_SIZE]
            else:
                indices = list(range(total_pages))

            per_page_lens = []
            per_page_vector = []
            for i in indices:
                page = pdf.pages[i]
                t = page.extract_text() or ""
                per_page_lens.append(len(t.strip()))
                # CAD 출력 도면은 페이지당 수만 개의 라인/곡선이 들어 있어 결정적 신호가 됨
                per_page_vector.append(len(page.lines) + len(page.curves))
            sampled_text_len = sum(per_page_lens)
            avg_per_page = sampled_text_len / len(per_page_lens) if per_page_lens else 0
            if len(per_page_lens) >= 4:
                back_lens = per_page_lens[-(len(per_page_lens) // 2):]
                back_avg = sum(back_lens) / len(back_lens)
            else:
                back_avg = avg_per_page
            avg_vector_objs = (
                sum(per_page_vector) / len(per_page_vector) if per_page_vector else 0
            )

            reject_reason = None
            if sampled_text_len < _PDF_PRECHECK_MIN_TEXT_LEN:
                reject_reason = "sum_too_low"
            elif avg_per_page < _PDF_PRECHECK_MIN_AVG_PER_PAGE:
                reject_reason = "avg_too_low"
            elif back_avg < _PDF_PRECHECK_MIN_BODY_AVG:
                reject_reason = "body_avg_too_low"
            elif avg_vector_objs >= _PDF_PRECHECK_MAX_VECTOR_OBJS_PER_PAGE:
                reject_reason = "too_many_vector_objs"

            if reject_reason:
                logger.warning(
                    "pdfplumber 사전 검사 실패(%s): 샘플 %d페이지(인덱스=%s) 합 %d자, "
                    "평균 %.1f자/p, 후반 평균 %.1f자/p, 벡터객체 평균 %.0f개/p "
                    "(임계 합>=%d, 평균>=%d, 후반>=%d, 벡터<%d) — 도면/이미지 PDF 추정, 빈 리스트 반환: %s",
                    reject_reason, len(per_page_lens), indices, sampled_text_len,
                    avg_per_page, back_avg, avg_vector_objs,
                    _PDF_PRECHECK_MIN_TEXT_LEN, _PDF_PRECHECK_MIN_AVG_PER_PAGE,
                    _PDF_PRECHECK_MIN_BODY_AVG, _PDF_PRECHECK_MAX_VECTOR_OBJS_PER_PAGE, path,
                )
                return pages
            logger.info(
                "pdfplumber 사전 검사 통과: 샘플 %d페이지(인덱스=%s) 합 %d자, "
                "평균 %.1f자/p, 후반 평균 %.1f자/p, 벡터객체 평균 %.0f개/p: %s",
                len(per_page_lens), indices, sampled_text_len,
                avg_per_page, back_avg, avg_vector_objs, path,
            )

            for i, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text()
                    if text:
                        text = _remove_pdf_hyphens(text)
                        text = _normalize_unicode(text)
                        text = _strip_null_chars(text)
                        text = _clean_common_noise(text)
                        text = _postprocess_pdf_text(text)
                        text = _join_korean_line_breaks(text)
                        pages.append((i, text))
                except Exception as page_err:
                    logger.debug(f"pdfplumber 페이지 {i} 추출 실패: {page_err}")
                    continue
    except Exception as e:
        logger.error(f"pdfplumber PDF 추출 실패: {path}, 에러: {e}")
        raise
    return pages


def _extract_pdf_pages_fitz(path: str) -> List[Tuple[int, str]]:
    """PyMuPDF(fitz) 기반 PDF 텍스트 추출 (폴백용).

    표 구조를 인식하여 의미있는 텍스트로 변환.
    텍스트 품질 문제가 감지돼도 OCR 폴백은 비활성화 — Tesseract는 품질 이슈로 사용 금지.
    OCR이 필요한 PDF는 enable_ocr=true로 Nemotron 경로(extract_pdf_pages_with_ocr)를 타야 함.
    """
    pages: List[Tuple[int, str]] = []
    try:
        with fitz.open(path) as doc:
            # 사전 검사: pdfplumber와 동일한 분산 샘플링 + 3조건 검사
            total_pages = len(doc)
            if total_pages >= _PDF_PRECHECK_SAMPLE_SIZE:
                front = list(range(4))
                mid = [total_pages // 2]
                back = list(range(max(4, total_pages - 3), total_pages))
                indices = sorted(set(front + mid + back))[:_PDF_PRECHECK_SAMPLE_SIZE]
            else:
                indices = list(range(total_pages))

            per_page_lens = []
            for i in indices:
                t = (doc[i].get_text() or "").strip()
                per_page_lens.append(len(t))
            sampled_text_len = sum(per_page_lens)
            avg_per_page = sampled_text_len / len(per_page_lens) if per_page_lens else 0
            if len(per_page_lens) >= 4:
                back_lens = per_page_lens[-(len(per_page_lens) // 2):]
                back_avg = sum(back_lens) / len(back_lens)
            else:
                back_avg = avg_per_page

            if (sampled_text_len < _PDF_PRECHECK_MIN_TEXT_LEN
                    or avg_per_page < _PDF_PRECHECK_MIN_AVG_PER_PAGE
                    or back_avg < _PDF_PRECHECK_MIN_BODY_AVG):
                logger.warning(
                    "fitz 사전 검사 실패: 샘플 %d페이지(인덱스=%s) 합 %d자, "
                    "평균 %.1f자/p, 후반 평균 %.1f자/p "
                    "(임계값 합>=%d, 평균>=%d, 후반>=%d) — 도면/이미지 PDF 추정, 빈 리스트 반환: %s",
                    len(per_page_lens), indices, sampled_text_len, avg_per_page, back_avg,
                    _PDF_PRECHECK_MIN_TEXT_LEN, _PDF_PRECHECK_MIN_AVG_PER_PAGE,
                    _PDF_PRECHECK_MIN_BODY_AVG, path,
                )
                return pages
            logger.info(
                "fitz 사전 검사 통과: 샘플 %d페이지(인덱스=%s) 합 %d자, "
                "평균 %.1f자/p, 후반 평균 %.1f자/p: %s",
                len(per_page_lens), indices, sampled_text_len, avg_per_page, back_avg, path,
            )

            for i, page in enumerate(doc, start=1):
                page_parts = []

                # 1. 표 추출 시도
                tables = page.find_tables()
                if tables and hasattr(tables, 'tables'):
                    for table in tables.tables:
                        try:
                            table_text = _extract_pdf_table(table)
                            if table_text:
                                page_parts.append(table_text)
                        except Exception as table_err:
                            logger.debug(f"PDF 표 추출 실패 (페이지 {i}): {table_err}")

                # 2. 일반 텍스트 추출
                text = _extract_pdf_page_text(page)
                if text:
                    # 표에서 추출한 텍스트와 중복 제거 (간단한 휴리스틱)
                    if page_parts:
                        for table_text in page_parts:
                            pass  # 복잡한 중복 제거는 생략, 둘 다 포함

                    page_parts.append(text)

                # 페이지 전체 텍스트 결합
                if page_parts:
                    combined_text = '\n\n'.join(page_parts)
                    pages.append((i, combined_text))

            # 3. 텍스트 품질 문제 감지 시 로그만 남김 (OCR 폴백 비활성화 — 품질 이슈)
            if pages and _pdf_text_has_extraction_problem(pages):
                logger.warning(
                    f"PDF 텍스트 품질 문제 감지, 좌표 정렬 결과 사용 (OCR 폴백 비활성화): {path}"
                )

    except Exception as e:
        logger.error(f"PDF 추출 실패 (PyMuPDF): {path}, 에러: {e}")
        raise
    return pages


def extract_pdf_pages(path: str) -> List[Tuple[int, str]]:
    """PDF → (page_no, text) 리스트

    pdfplumber(pdfminer.six)를 우선 사용하고, 미설치 시 PyMuPDF로 폴백.
    pdfplumber는 HWP→PDF 변환 문서의 CMap 해석이 우수하여
    숫자·괄호·가운뎃점 등 특수문자가 정상 추출됨.
    """
    # pdfplumber 우선 사용
    if PDFPLUMBER_AVAILABLE:
        try:
            pages = _extract_pdf_pages_pdfplumber(path)
            # 빈 리스트는 사전검사로 거른 도면/이미지 PDF — PyMuPDF로 폴백해도 같은 결과이므로 그대로 반환
            return pages
        except Exception as e:
            logger.warning(f"pdfplumber 추출 실패, PyMuPDF로 폴백: {path}, 에러: {e}")

    # PyMuPDF 폴백 (pdfplumber 미설치 또는 실제 예외 발생 시)
    return _extract_pdf_pages_fitz(path)


# ════════════════════════════════════════════════════════════════════
# OCR 모드 PDF 추출
# ════════════════════════════════════════════════════════════════════

def _extract_image_objects_from_page(doc, page) -> List[Tuple[bytes, str]]:
    """페이지의 이미지 객체별 (bytes, mime) 리스트.

    PDF에 정식 등록된 이미지 객체만 반환. vector path로만 그려진 도형/도면은 포함되지 않음.
    실패한 이미지는 건너뜀.
    """
    results: List[Tuple[bytes, str]] = []
    img_list = page.get_images(full=True)
    for img_info in img_list:
        xref = img_info[0]
        try:
            base_img = doc.extract_image(xref)
            img_bytes = base_img["image"]
            ext = base_img.get("ext", "png")
            if ext == "jpg":
                ext = "jpeg"
            mime = f"image/{ext}"
            results.append((img_bytes, mime))
        except Exception as e:
            logger.warning("이미지 객체 추출 실패 (xref=%d): %s", xref, e)
    return results


# upscale 후 최대 한 변의 픽셀 수.
# vLLM이 거대 이미지를 거부(400 Bad Request)하는 것을 방지.
# Gemma-3 vision encoder가 어차피 일정 해상도로 normalize 하므로 너무 키워도 효과 없음.
_OCR_UPSCALE_MAX_DIM_PX = 2000


def _maybe_upscale_image(
    img_bytes: bytes,
    mime: str,
    threshold_px: int = 800,
    factor: float = 2.0,
) -> Tuple[bytes, str]:
    """이미지가 작으면 Lanczos로 upscale.

    OCR 정확도 개선용. PDF에 임베드된 작은 이미지(예: 다이어그램 안의 작은 라벨)에서
    글자 인식률이 떨어지는 것을 보완한다.

    동작:
    - max(width, height) >= threshold_px: 원본 그대로 반환
    - 미만: factor 배 Lanczos upscale 후 PNG로 변환
    - upscale 결과가 _OCR_UPSCALE_MAX_DIM_PX 초과: max로 cap (vLLM 400 에러 방지)

    PIL 미설치 시 원본 그대로 반환 (안전 폴백).
    """
    try:
        from PIL import Image
        import io
    except ImportError:
        logger.debug("PIL 미설치 — upscale 스킵")
        return img_bytes, mime

    try:
        img = Image.open(io.BytesIO(img_bytes))
        max_side = max(img.size)
        if max_side >= threshold_px:
            return img_bytes, mime  # 충분히 큰 이미지는 그대로

        # PNG는 CMYK 저장 불가 → RGB로 변환. P(팔레트) 등 기타 모드도 PNG 호환되게 정규화.
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        new_w = int(img.width * factor)
        new_h = int(img.height * factor)

        # MAX_DIM cap — upscale 결과가 너무 크면 vLLM이 거부할 수 있어 비율 유지하며 축소
        new_max = max(new_w, new_h)
        if new_max > _OCR_UPSCALE_MAX_DIM_PX:
            shrink = _OCR_UPSCALE_MAX_DIM_PX / new_max
            new_w = int(new_w * shrink)
            new_h = int(new_h * shrink)
            logger.debug(
                "upscale 결과가 MAX_DIM(%d) 초과 → %dx%d로 cap",
                _OCR_UPSCALE_MAX_DIM_PX, new_w, new_h,
            )

        # Lanczos: 고품질 down/up-sampling 알고리즘
        img_upscaled = img.resize((new_w, new_h), Image.LANCZOS)

        # PNG로 통일 (무손실)
        out = io.BytesIO()
        # 알파 채널 등 보존 위해 RGBA → RGB 변환은 하지 않음 (PNG는 RGBA 지원)
        img_upscaled.save(out, format="PNG", optimize=False)
        logger.debug(
            "이미지 upscale: %dx%d → %dx%d",
            img.width, img.height, new_w, new_h,
        )
        return out.getvalue(), "image/png"
    except Exception as e:
        # upscale 실패 시 원본으로 폴백 (OCR 자체는 계속 진행 가능하게)
        logger.warning("이미지 upscale 실패, 원본 사용: %s", e)
        return img_bytes, mime


def _has_drawings(page) -> bool:
    """페이지에 vector 객체(도면 등)가 있는지"""
    try:
        return len(page.get_drawings()) > 0
    except Exception:
        return False


def _ocr_image_bytes_safe(
    ocr_client,
    img_bytes: bytes,
    mime: str,
    upscale_threshold_px: int = 800,
    upscale_factor: float = 2.0,
    context_label: str = "image",
) -> str:
    """이미지 바이트 → OCR 텍스트 (upscale + 호출 + 검증 + 예외 처리).

    PDF 외 형식(DOCX/PPTX/XLSX/HWP 등)에서 추출한 이미지를 OCR로 변환할 때 공통으로 사용.
    실패하거나 텍스트가 없으면 빈 문자열 반환 — 호출 측은 결과가 truthy인지만 확인.
    """
    try:
        ocr_bytes, ocr_mime = _maybe_upscale_image(
            img_bytes, mime,
            threshold_px=upscale_threshold_px,
            factor=upscale_factor,
        )
        ocr_text, elapsed = ocr_client.extract_from_image_bytes(ocr_bytes, ocr_mime)
        if ocr_client.is_no_text(ocr_text):
            logger.debug("%s OCR: 텍스트 없음, 스킵", context_label)
            return ""
        logger.info("%s OCR 성공: %d자 (%.2fs)", context_label, len(ocr_text), elapsed)
        return ocr_text
    except Exception as e:
        logger.warning("%s OCR 실패: %s", context_label, e)
        return ""


def _render_page_to_png(page, scale: float = 2.0) -> bytes:
    """페이지를 PNG 바이트로 렌더링"""
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return pix.tobytes("png")


def extract_pdf_pages_with_ocr(
    path: str,
    ocr_client,
    page_text_threshold: int = 50,
    render_scale: float = 2.0,
    image_upscale_threshold_px: int = 800,
    image_upscale_factor: float = 2.0,
    page_drawings_threshold: int = 50,
    text_layer_corruption_gate: int = 6,
) -> List[Tuple[int, str]]:
    """OCR 모드 PDF → (page_no, text) 리스트.

    페이지별 처리 분기:
    - 텍스트 ≥ threshold AND corruption < gate: PyMuPDF 텍스트 + (이미지 있으면) 객체별 OCR (옵션 A)
      └─ + raster 이미지 없고 vector 도형 > page_drawings_threshold면 페이지 통째 OCR 추가 (보강)
    - 텍스트 ≥ threshold BUT corruption ≥ gate: 텍스트레이어 깨짐(임베디드 폰트 ToUnicode CMap
      손상 → 유니코드 쓰레기) → 텍스트레이어 폐기하고 페이지 통째 OCR (신규 폴백)
    - 텍스트 < threshold + (이미지 객체 또는 vector 도형): 페이지 통째 OCR (옵션 B 폴백)
    - 텍스트·이미지 모두 없음: 스킵

    Args:
        path: PDF 경로
        ocr_client: Nemotron OCR 클라이언트 (NemotronOCRClient 인스턴스)
        page_text_threshold: 텍스트 임계값 (자, 미만이면 이미지 페이지로 판정)
        render_scale: 페이지 통째 렌더링 시 해상도 배율
        page_drawings_threshold: CASE 1 페이지에서 vector 도형 보강 OCR 트리거 임계값.
            PowerPoint/Visio→PDF 변환된 도면(get_images()에 안 잡히는 path 객체)을 캡처.
    """
    pages: List[Tuple[int, str]] = []

    try:
        with fitz.open(path) as doc:
            total = len(doc)
            logger.info(
                "OCR 모드 PDF 추출 시작: %s (총 %d페이지, threshold=%d자, scale=%.1f)",
                path, total, page_text_threshold, render_scale,
            )

            for i, page in enumerate(doc, start=1):
                page_text = page.get_text().strip()
                text_len = len(page_text)
                img_count = len(page.get_images())

                page_parts: List[str] = []

                # 텍스트레이어 신뢰도 판정: 길이 충분 + corruption 낮음.
                # 임베디드 폰트의 ToUnicode CMap이 깨진 PDF는 get_text()가 유니코드
                # 쓰레기(예: 한글→키릴/아랍 블록)를 반환하는데, 길이만 보면 이를 놓친다.
                # corruption 게이트로 걸러 깨진 텍스트레이어는 OCR로 폴백시킨다.
                text_score = None
                if text_len >= page_text_threshold:
                    text_score = score_chunk_corruption(page_text).score

                if text_len >= page_text_threshold and text_score >= text_layer_corruption_gate:
                    # CASE 1-b: 텍스트레이어 깨짐 → 폐기하고 페이지 통째 OCR
                    logger.warning(
                        "page %d 텍스트레이어 corruption=%d ≥ gate=%d → 통째 OCR 폴백",
                        i, text_score, text_layer_corruption_gate,
                    )
                    try:
                        png_bytes = _render_page_to_png(page, scale=render_scale)
                        ocr_text, elapsed = ocr_client.extract_from_image_bytes(png_bytes, "image/png")
                        if not ocr_client.is_no_text(ocr_text):
                            page_parts.append(ocr_text)
                            logger.info(
                                "page %d 깨진 텍스트레이어 OCR 폴백: %d자 (%.2fs)",
                                i, len(ocr_text), elapsed,
                            )
                    except Exception as e:
                        logger.warning("page %d 깨진 텍스트레이어 OCR 폴백 실패: %s", i, e)

                elif text_len >= page_text_threshold:
                    # CASE 1: 텍스트 충분 → PyMuPDF 텍스트 + 옵션 A 이미지별 OCR
                    # 기존 추출 경로와 동일한 cleaning 적용 (목차 leader dots, CID,
                    # 제어문자, NBSP 등 제거). OCR 결과에는 cleaning을 적용하지 않음
                    # (markdown 표 형식 보존).
                    cleaned_text = _clean_common_noise(
                        _normalize_unicode(_strip_null_chars(page_text))
                    ).strip()
                    if cleaned_text:
                        page_parts.append(cleaned_text)
                    if img_count > 0:
                        image_objects = _extract_image_objects_from_page(doc, page)
                        for img_idx, (img_bytes, mime) in enumerate(image_objects, start=1):
                            try:
                                # 작은 이미지는 upscale (다이어그램 안 작은 글자 인식률 ↑)
                                ocr_bytes, ocr_mime = _maybe_upscale_image(
                                    img_bytes, mime,
                                    threshold_px=image_upscale_threshold_px,
                                    factor=image_upscale_factor,
                                )
                                ocr_text, elapsed = ocr_client.extract_from_image_bytes(ocr_bytes, ocr_mime)
                                if ocr_client.is_no_text(ocr_text):
                                    logger.debug("page %d img %d: 텍스트 없음", i, img_idx)
                                    continue
                                # 마커 없이 그냥 추가. page_parts는 "\n\n"으로 join되어
                                # 자연스러운 단락 구분이 유지됨. 검색 시 "[이미지 OCR]" 같은
                                # 메타 단어가 인덱싱되거나 LLM 답변에 노출되는 것을 방지.
                                page_parts.append(ocr_text)
                                logger.debug(
                                    "page %d img %d: %d자 (%.2fs)",
                                    i, img_idx, len(ocr_text), elapsed,
                                )
                            except Exception as e:
                                logger.warning("page %d img %d OCR 실패: %s", i, img_idx, e)
                    else:
                        # raster 이미지 없음 → vector path 도형이 많으면 PowerPoint/Visio→PDF
                        # 변환된 도면 가능성. 페이지 통째 OCR로 도면 안 글자 보강.
                        try:
                            drawings_count = len(page.get_drawings())
                        except Exception:
                            drawings_count = 0
                        if drawings_count > page_drawings_threshold:
                            try:
                                png_bytes = _render_page_to_png(page, scale=render_scale)
                                ocr_text, elapsed = ocr_client.extract_from_image_bytes(png_bytes, "image/png")
                                if not ocr_client.is_no_text(ocr_text):
                                    page_parts.append(ocr_text)
                                    logger.debug(
                                        "page %d vector 보강 OCR: drawings=%d, %d자 (%.2fs)",
                                        i, drawings_count, len(ocr_text), elapsed,
                                    )
                            except Exception as e:
                                logger.warning("page %d vector 보강 OCR 실패: %s", i, e)

                elif img_count > 0 or _has_drawings(page):
                    # CASE 2: 텍스트 적고 이미지/도형 있음 → 페이지 통째 OCR
                    try:
                        png_bytes = _render_page_to_png(page, scale=render_scale)
                        ocr_text, elapsed = ocr_client.extract_from_image_bytes(png_bytes, "image/png")
                        if ocr_client.is_no_text(ocr_text):
                            logger.debug("page %d 통째 OCR: 텍스트 없음, 스킵", i)
                        else:
                            page_parts.append(ocr_text)
                            logger.debug(
                                "page %d 통째 OCR: %d자 (%.2fs)",
                                i, len(ocr_text), elapsed,
                            )
                    except Exception as e:
                        logger.warning("page %d 통째 OCR 실패: %s", i, e)
                else:
                    # CASE 3: 텍스트·이미지 모두 없음 → 스킵
                    logger.debug("page %d: 비어있음, 스킵", i)
                    continue

                if page_parts:
                    combined = "\n\n".join(page_parts)
                    pages.append((i, combined))

            logger.info(
                "OCR 모드 PDF 추출 완료: %s (%d/%d 페이지에서 텍스트 추출)",
                path, len(pages), total,
            )
    except Exception as e:
        logger.error("OCR 모드 PDF 추출 실패: %s, 에러: %s", path, e)
        raise

    return pages


def _extract_pdf_table(table) -> str:
    """PyMuPDF 표 객체에서 구조화된 텍스트 추출"""
    try:
        rows_text = []
        table_data = table.extract()
        
        for row in table_data:
            cells_text = []
            for cell in row:
                if cell:
                    cell_str = str(cell).strip()
                    if cell_str and not _is_formula_or_noise(cell_str):
                        cells_text.append(cell_str)
            
            if cells_text:
                rows_text.append(' | '.join(cells_text))
        
        return '\n'.join(rows_text) if rows_text else ''
    except Exception as e:
        logger.debug(f"표 추출 중 오류: {e}")
        return ''


def _calculate_timeout(file_path: str) -> int:
    """파일 크기에 따른 동적 타임아웃 계산
    
    - 10MB 이하: 60초
    - 10-100MB: 180초 (3분)
    - 100-500MB: 300초 (5분)
    - 500MB 이상: 600초 (10분)
    """
    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        if file_size_mb <= 10:
            return 60
        elif file_size_mb <= 100:
            return 180
        elif file_size_mb <= 500:
            return 300
        else:
            return 600
    except:
        return 180  # 기본값 3분


def extract_docx_pages_via_pdf(path: str, ocr_client=None, **ocr_kwargs) -> List[Tuple[int, str]]:
    """DOCX → PDF 변환 후 페이지별 추출 (LibreOffice 사용)

    LibreOffice를 사용하여 DOCX를 PDF로 변환한 후 PyMuPDF로 페이지별 추출.
    ocr_client가 주어지면 변환된 PDF에 OCR도 함께 적용 (이미지 안 글자 캡처).
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.splitext(os.path.basename(path))[0]
            pdf_path = os.path.join(tmpdir, base + ".pdf")

            timeout = _calculate_timeout(path)
            file_size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info("DOCX → PDF 변환 시작: %s (%.1fMB, 타임아웃: %d초)", path, file_size_mb, timeout)

            pdf_cmd = [
                "soffice",
                "--headless",
                "--invisible",
                "--nocrashreport",
                "--nodefault",
                "--nofirststartwizard",
                "--nolockcheck",
                "--nologo",
                "--norestore",
                "--convert-to", "pdf",
                "--outdir", tmpdir,
                path,
            ]

            pdf_result = subprocess.run(pdf_cmd, capture_output=True, timeout=timeout)

            if pdf_result.returncode != 0 or not os.path.exists(pdf_path):
                logger.error(
                    "DOCX → PDF 변환 실패(returncode=%s, stderr=%s)",
                    pdf_result.returncode,
                    pdf_result.stderr.decode("utf-8", errors="ignore"),
                )
                raise RuntimeError("DOCX → PDF 변환에 실패했습니다.")

            if ocr_client is not None:
                pages = extract_pdf_pages_with_ocr(pdf_path, ocr_client=ocr_client, **ocr_kwargs)
            else:
                pages = extract_pdf_pages(pdf_path)

            logger.info("DOCX → PDF 변환 성공: %s (페이지 %d개, ocr=%s)", path, len(pages), ocr_client is not None)
            return pages

    except Exception as e:
        logger.error(f"DOCX → PDF 변환 실패: {path}, 에러: {e}")
        raise


def extract_docx_pages(path: str, use_libreoffice: bool = True, ocr_client=None, **ocr_kwargs) -> List[Tuple[int, str]]:
    """DOCX → (page_no, text) 리스트

    Args:
        path: DOCX 파일 경로
        use_libreoffice: True이면 LibreOffice로 PDF 변환 후 추출 (페이지 정보 포함)
                        False이면 python-docx로 직접 추출 (페이지 정보 없음, 빠름)
        ocr_client: OCR 클라이언트 (LibreOffice 경로에서만 동작). fallback 경로는 OCR 미지원.
    - 취소선(strikethrough) 텍스트 자동 제외
    """
    if use_libreoffice:
        try:
            return extract_docx_pages_via_pdf(path, ocr_client=ocr_client, **ocr_kwargs)
        except Exception as e:
            logger.warning(f"LibreOffice 변환 실패, python-docx로 fallback (OCR 미지원): {e}")

    # python-docx로 직접 추출 (fallback)
    # body 전체를 순회하며 paragraph, table을 문서 순서대로 처리
    try:
        document = docx.Document(path)
        texts: List[str] = []

        W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

        def _is_strikethrough_run(r_elem) -> bool:
            """run 요소에 취소선(strike/dstrike)이 적용되었는지 확인"""
            rPr = r_elem.find(f'{{{W_NS}}}rPr')
            if rPr is None:
                return False
            strike = rPr.find(f'{{{W_NS}}}strike')
            dstrike = rPr.find(f'{{{W_NS}}}dstrike')
            if strike is not None and strike.get(f'{{{W_NS}}}val', 'true') != 'false':
                return True
            if dstrike is not None and dstrike.get(f'{{{W_NS}}}val', 'true') != 'false':
                return True
            return False

        def _extract_para_text(p_elem) -> str:
            """문단에서 취소선 제외한 텍스트 추출"""
            parts = []
            for run in p_elem.iter(f'{{{W_NS}}}r'):
                if _is_strikethrough_run(run):
                    continue
                for t_elem in run.iter(f'{{{W_NS}}}t'):
                    if t_elem.text:
                        parts.append(t_elem.text)
            return ''.join(parts)

        # body의 직계 자식을 순서대로 처리 (문서 순서 보장)
        for child in document.element.body:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

            if tag == 'p':  # 문단
                txt = _extract_para_text(child)
                txt = _clean_common_noise(_normalize_unicode(_strip_null_chars(txt))).strip()
                if txt and not _is_formula_or_noise(txt):
                    texts.append(txt)

            elif tag == 'tbl':  # 표
                table_rows = []
                for tr in child.iter(f'{{{W_NS}}}tr'):
                    cells_text = []
                    for tc in tr.iter(f'{{{W_NS}}}tc'):
                        cell_parts = []
                        for run in tc.iter(f'{{{W_NS}}}r'):
                            if _is_strikethrough_run(run):
                                continue
                            for t_elem in run.iter(f'{{{W_NS}}}t'):
                                if t_elem.text:
                                    cell_parts.append(t_elem.text)
                        cell_txt = _clean_common_noise(_normalize_unicode(_strip_null_chars(''.join(cell_parts)))).strip()
                        if cell_txt and not _is_formula_or_noise(cell_txt):
                            cells_text.append(cell_txt)
                    if cells_text:
                        table_rows.append(" | ".join(cells_text))
                if table_rows:
                    texts.append("\n".join(table_rows))

        if not texts:
            return []

        combined = "\n".join(texts)
        combined = _postprocess_pdf_text(combined)
        logger.info("DOCX 추출 완료: %s (문단 %d개)", path, len(texts))
        return [(1, combined)]
    except Exception as e:
        logger.error(f"DOCX 추출 실패: {path}, 에러: {e}")
        raise


_XLSX_MEDIA_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".webp": "image/webp",
}


def _ocr_zipfile_media(
    path: str,
    media_prefix: str,
    ocr_client,
    upscale_threshold_px: int = 800,
    upscale_factor: float = 2.0,
    context_label: str = "media",
) -> List[str]:
    """zipfile 기반 형식(.xlsx/.pptx/.hwpx 등)의 media 폴더에서 이미지를 OCR.

    Args:
        path: 압축 파일 경로
        media_prefix: media 폴더 prefix (예: "xl/media/", "ppt/media/", "BinData/")
        ocr_client: OCR 클라이언트
        context_label: 로그용 라벨

    Returns:
        OCR 텍스트 리스트 (빈 결과/실패한 이미지는 제외)
    """
    import zipfile

    results: List[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            media_names = sorted([n for n in z.namelist() if n.startswith(media_prefix) and not n.endswith("/")])
            if not media_names:
                logger.debug("%s: media 항목 없음 (prefix=%s)", context_label, media_prefix)
                return results

            for idx, name in enumerate(media_names, start=1):
                ext = os.path.splitext(name)[1].lower()
                mime = _XLSX_MEDIA_MIME.get(ext)
                if not mime:
                    # 알 수 없는 확장자는 스킵 (워드프로세서가 비-이미지 파일을 BinData에 둘 수 있음)
                    logger.debug("%s: 비-이미지 미디어 스킵 (%s)", context_label, name)
                    continue
                try:
                    img_bytes = z.read(name)
                except Exception as e:
                    logger.warning("%s: %s 읽기 실패: %s", context_label, name, e)
                    continue

                ocr_text = _ocr_image_bytes_safe(
                    ocr_client, img_bytes, mime,
                    upscale_threshold_px=upscale_threshold_px,
                    upscale_factor=upscale_factor,
                    context_label=f"{context_label} img {idx}/{len(media_names)} ({os.path.basename(name)})",
                )
                if ocr_text:
                    results.append(ocr_text)
    except Exception as e:
        logger.warning("%s OCR 전체 실패: %s", context_label, e)

    return results


def _build_xlsx_sheet_media_map(path: str) -> Dict[str, List[str]]:
    """XLSX → {sheet_name: [media_zip_path, ...]} 매핑 build.

    XLSX zipfile 구조를 따라 시트별로 어떤 미디어 파일(이미지)이 참조되는지 추적:
    1. xl/workbook.xml → <sheet name="..." r:id="rIdN"/>
    2. xl/_rels/workbook.xml.rels → rIdN → "worksheets/sheetN.xml"
    3. xl/worksheets/_rels/sheetN.xml.rels → "../drawings/drawingM.xml" 참조
    4. xl/drawings/_rels/drawingM.xml.rels → "../media/imageX.png" 참조

    실패해도 빈 dict 반환 (caller가 폴백으로 일괄 OCR 처리 가능).
    """
    import zipfile
    from xml.etree import ElementTree as ET

    MAIN_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

    result: Dict[str, List[str]] = {}
    try:
        with zipfile.ZipFile(path) as z:
            names_set = set(z.namelist())

            # 1. xl/workbook.xml — sheet name → r:id
            if 'xl/workbook.xml' not in names_set:
                return result
            try:
                wb_root = ET.fromstring(z.read('xl/workbook.xml'))
            except ET.ParseError:
                return result

            sheet_name_to_rid: Dict[str, str] = {}
            for sheet in wb_root.iter(f'{MAIN_NS}sheet'):
                nm = sheet.get('name')
                rid = sheet.get(f'{REL_NS}id')
                if nm and rid:
                    sheet_name_to_rid[nm] = rid

            # 2. xl/_rels/workbook.xml.rels — r:id → sheet target
            if 'xl/_rels/workbook.xml.rels' not in names_set:
                return result
            try:
                wb_rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            except ET.ParseError:
                return result

            rid_to_target: Dict[str, str] = {}
            for rel in wb_rels:
                rid = rel.get('Id')
                tgt = rel.get('Target', '')
                rtype = rel.get('Type', '')
                if rid and tgt and 'worksheet' in rtype.lower():
                    rid_to_target[rid] = tgt  # e.g. "worksheets/sheet1.xml"

            # 3, 4. 각 시트의 _rels → drawing → 미디어
            for sheet_name, rid in sheet_name_to_rid.items():
                target = rid_to_target.get(rid)
                if not target:
                    continue
                # target = "worksheets/sheet1.xml" → rels: "xl/worksheets/_rels/sheet1.xml.rels"
                rels_path = 'xl/' + target.rsplit('/', 1)[0] + '/_rels/' + target.rsplit('/', 1)[-1] + '.rels'
                if rels_path not in names_set:
                    continue
                try:
                    sheet_rels = ET.fromstring(z.read(rels_path))
                except ET.ParseError:
                    continue

                drawing_targets: List[str] = []
                for rel in sheet_rels:
                    if 'drawing' in rel.get('Type', '').lower():
                        drawing_targets.append(rel.get('Target', ''))  # "../drawings/drawing1.xml"

                media_paths: List[str] = []
                for d_target in drawing_targets:
                    # "../drawings/drawing1.xml" → rels: "xl/drawings/_rels/drawing1.xml.rels"
                    d_filename = d_target.split('/')[-1]
                    d_rels_path = 'xl/drawings/_rels/' + d_filename + '.rels'
                    if d_rels_path not in names_set:
                        continue
                    try:
                        d_rels = ET.fromstring(z.read(d_rels_path))
                    except ET.ParseError:
                        continue
                    for rel in d_rels:
                        if 'image' in rel.get('Type', '').lower():
                            t = rel.get('Target', '')
                            # 절대 path: "../media/image1.png" → "xl/media/image1.png"
                            if t.startswith('../'):
                                media_paths.append('xl/' + t[3:])
                            elif t.startswith('/'):
                                media_paths.append(t.lstrip('/'))
                            else:
                                media_paths.append('xl/drawings/' + t)

                if media_paths:
                    result[sheet_name] = media_paths
    except Exception as e:
        logger.warning("XLSX 시트-미디어 매핑 build 실패: %s, 에러: %s", path, e)

    return result


def extract_xlsx_rows(
    path: str,
    ocr_client=None,
    image_upscale_threshold_px: int = 800,
    image_upscale_factor: float = 2.0,
) -> List[Tuple[str, int, str]]:
    """XLSX → [(sheet_name, row_index, text), ...]

    data_only=True로 수식 결과값만 추출하고, 노이즈 필터링.
    ocr_client가 주어지면 각 시트에 박힌 이미지를 OCR해 같은 시트의 마지막 row 다음에 추가 row로 inline 삽입.
    (별도 가상 시트가 아니라 본문 시트와 같은 sheet_name으로 — 검색 시 컨텍스트 단절 방지)
    """
    # 시트별 미디어 매핑 (ocr_client가 있을 때만 build)
    sheet_media_map: Dict[str, List[str]] = (
        _build_xlsx_sheet_media_map(path) if ocr_client is not None else {}
    )

    # OCR 호출 시 zipfile에서 이미지 바이트를 직접 읽어와야 하므로 별도 핸들로 열어둠
    import zipfile as _zipfile
    media_zip = _zipfile.ZipFile(path) if (ocr_client is not None and sheet_media_map) else None

    def _ocr_rows_for_sheet(sheet_name: str, start_row: int) -> List[Tuple[str, int, str]]:
        """이 시트에 매핑된 미디어들을 OCR해 (sheet_name, row, ocr_text) 리스트 반환."""
        if media_zip is None or sheet_name not in sheet_media_map:
            return []
        result_rows: List[Tuple[str, int, str]] = []
        next_row = start_row
        for media_path in sheet_media_map[sheet_name]:
            ext = os.path.splitext(media_path)[1].lower()
            mime = _XLSX_MEDIA_MIME.get(ext)
            if not mime:
                continue
            try:
                img_bytes = media_zip.read(media_path)
            except Exception as e:
                logger.debug("XLSX 미디어 읽기 실패 (%s): %s", media_path, e)
                continue
            ocr_text = _ocr_image_bytes_safe(
                ocr_client, img_bytes, mime,
                upscale_threshold_px=image_upscale_threshold_px,
                upscale_factor=image_upscale_factor,
                context_label=f"XLSX [{sheet_name}] {os.path.basename(media_path)}",
            )
            if not ocr_text:
                continue
            cleaned = _clean_common_noise(_normalize_unicode(_strip_null_chars(ocr_text))).strip()
            if cleaned:
                next_row += 1
                result_rows.append((sheet_name, next_row, cleaned))
        return result_rows

    def _read_sheets(wb):
        rows_with_meta: List[Tuple[str, int, str]] = []
        total_kept = 0
        truncated = False
        for sheet in wb.worksheets:
            sheet_name = sheet.title
            sheet_state = getattr(sheet, "sheet_state", "visible")
            if _XLSX_SKIP_HIDDEN_SHEETS and sheet_state != "visible":
                logger.info(
                    "XLSX 숨김 시트 스킵: sheet=%s, state=%s, path=%s",
                    sheet_name, sheet_state, path,
                )
                continue

            sheet_kept = 0
            consecutive_blanks = 0
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                if total_kept >= _XLSX_MAX_TOTAL_ROWS:
                    truncated = True
                    logger.warning(
                        "XLSX 전체 추출 행 상한 도달: limit=%d, path=%s, current_sheet=%s",
                        _XLSX_MAX_TOTAL_ROWS, path, sheet_name,
                    )
                    break
                if sheet_kept >= _XLSX_MAX_ROWS_PER_SHEET:
                    logger.warning(
                        "XLSX 시트 추출 행 상한 도달, 다음 시트로: sheet=%s, limit=%d, path=%s",
                        sheet_name, _XLSX_MAX_ROWS_PER_SHEET, path,
                    )
                    break

                values = []
                for v in row:
                    if v is not None:
                        v_str = str(v).strip()
                        if v_str and not _is_formula_or_noise(v_str):
                            values.append(v_str)
                if values:
                    joined = " | ".join(values)
                    joined = _normalize_unicode(joined)
                    joined = _strip_null_chars(joined)
                    joined = _clean_common_noise(joined)
                    if joined:
                        rows_with_meta.append((sheet_name, row_idx, joined))
                        sheet_kept += 1
                        total_kept += 1
                        consecutive_blanks = 0
                        continue
                # 값이 없거나 정제 후 비었음 → 빈 행으로 카운트
                consecutive_blanks += 1
                if consecutive_blanks >= _XLSX_BLANK_ROW_TERMINATE:
                    logger.info(
                        "XLSX 연속 빈 행 %d개 감지, 시트 조기 종료: sheet=%s, last_row=%d, path=%s",
                        _XLSX_BLANK_ROW_TERMINATE, sheet_name, row_idx, path,
                    )
                    break

            # OCR: 이 시트에 매핑된 이미지를 OCR해 같은 sheet_name의 row로 inline 추가
            # 본문 시트 흐름과 같은 sheet_name이라 검색 시 컨텍스트 단절이 적음.
            ocr_rows = _ocr_rows_for_sheet(sheet_name, start_row=sheet_kept)
            if ocr_rows:
                rows_with_meta.extend(ocr_rows)
                total_kept += len(ocr_rows)
                logger.info(
                    "XLSX OCR inline: 시트 [%s] 본문 %d행 다음에 OCR %d행 추가",
                    sheet_name, sheet_kept, len(ocr_rows),
                )

            logger.info(
                "XLSX 시트 추출 완료: sheet=%s, kept_rows=%d, path=%s",
                sheet_name, sheet_kept, path,
            )
            if truncated:
                break

        logger.info(
            "XLSX 추출 요약: total_rows=%d, sheets_processed=%d, truncated=%s, path=%s",
            total_kept,
            sum(
                1 for s in wb.worksheets
                if not (_XLSX_SKIP_HIDDEN_SHEETS and getattr(s, "sheet_state", "visible") != "visible")
            ),
            truncated, path,
        )
        return rows_with_meta

    def _patch_xlsx_defined_names(src_path: str) -> str:
        """workbook.xml에서 잘못된 definedName 항목을 제거한 임시 파일 생성"""
        import zipfile
        import tempfile
        from xml.etree import ElementTree as ET

        patched_path = tempfile.mktemp(suffix='.xlsx')
        with zipfile.ZipFile(src_path, 'r') as zin, zipfile.ZipFile(patched_path, 'w') as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'xl/workbook.xml':
                    try:
                        root = ET.fromstring(data)
                        ns = {'': root.tag.split('}')[0] + '}'} if '}' in root.tag else {}
                        ns_prefix = ns.get('', '')
                        for dn_list in root.findall(f'.//{ns_prefix}definedNames'):
                            for dn in list(dn_list):
                                if dn.text and '#' in dn.text:
                                    dn_list.remove(dn)
                        data = ET.tostring(root, xml_declaration=True, encoding='UTF-8')
                    except Exception:
                        pass  # 패치 실패 시 원본 유지
                zout.writestr(item, data)
        return patched_path

    try:
        try:
            wb = load_workbook(path, data_only=True)
            return _read_sheets(wb)
        except ValueError as e:
            if "invalid" in str(e).lower() and ("xml" in str(e).lower() or "print titles" in str(e).lower()):
                logger.warning("XLSX 정상 로드 실패, 잘못된 definedName 패치 후 재시도: %s", path)
                patched = None
                try:
                    patched = _patch_xlsx_defined_names(path)
                    wb = load_workbook(patched, data_only=True)
                    return _read_sheets(wb)
                except Exception as e2:
                    logger.error(f"XLSX 패치 후에도 실패: {path}, 에러: {e2}")
                    raise
                finally:
                    if patched:
                        try:
                            os.remove(patched)
                        except OSError:
                            pass
            logger.error(f"XLSX 추출 실패: {path}, 에러: {e}")
            raise
        except Exception as e:
            logger.error(f"XLSX 추출 실패: {path}, 에러: {e}")
            raise
    finally:
        # OCR용으로 별도 열어둔 zipfile 핸들 닫기
        if media_zip is not None:
            try:
                media_zip.close()
            except Exception:
                pass


def extract_xls_rows(path: str) -> List[Tuple[str, int, str]]:
    """XLS → [(sheet_name, row_index, text), ...]
    
    수식이나 노이즈 필터링
    """
    try:
        book = xlrd.open_workbook(path)
        rows_with_meta: List[Tuple[str, int, str]] = []
        for sheet in book.sheets():
            sheet_name = sheet.name
            for rx in range(sheet.nrows):
                row_values = sheet.row_values(rx)
                values = []
                for v in row_values:
                    if v is not None:
                        v_str = str(v).strip()
                        if v_str and not _is_formula_or_noise(v_str):
                            values.append(v_str)
                
                if values:
                    joined = " | ".join(values)
                    joined = _normalize_unicode(joined)
                    joined = _strip_null_chars(joined)
                    joined = _clean_common_noise(joined)
                    if joined:
                        rows_with_meta.append((sheet_name, rx + 1, joined))
        return rows_with_meta
    except Exception as e:
        logger.error(f"XLS 추출 실패: {path}, 에러: {e}")
        raise


def extract_csv_rows(path: str) -> List[Tuple[str, int, str]]:
    """CSV → [(sheet_name, row_index, text), ...]
    
    수식이나 노이즈 필터링
    """
    rows_with_meta: List[Tuple[str, int, str]] = []
    
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            with open(path, "r", encoding=enc) as f:
                reader = csv.reader(f)
                for idx, row in enumerate(reader, start=1):
                    values = []
                    for v in row:
                        if v:
                            v_str = v.strip()
                            if v_str and not _is_formula_or_noise(v_str):
                                values.append(v_str)
                    
                    if values:
                        joined = " | ".join(values)
                        joined = _normalize_unicode(joined)
                        joined = _strip_null_chars(joined)
                        joined = _clean_common_noise(joined)
                        if joined:
                            rows_with_meta.append(("CSV", idx, joined))
            return rows_with_meta
        except UnicodeDecodeError:
            continue
    
    raise RuntimeError(f"CSV 파일 인코딩을 알 수 없습니다: {path}")


def extract_pptx_text(path: str) -> str:
    """PPTX → 전체 텍스트 (레거시)"""
    pages = extract_pptx_pages(path)
    return "\n".join(text for _, text in pages)


def extract_pptx_pages(
    path: str,
    ocr_client=None,
    image_upscale_threshold_px: int = 800,
    image_upscale_factor: float = 2.0,
) -> List[Tuple[int, str]]:
    """PPTX → (slide_no, text) 리스트

    표 구조를 명확히 구분하여 추출.
    ocr_client가 주어지면 슬라이드 내 PICTURE shape에서 이미지를 추출해 OCR로 텍스트 변환.
    """
    try:
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        def iter_all_shapes(shapes):
            for shape in shapes:
                yield shape
                if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.GROUP:
                    for sub in iter_all_shapes(shape.shapes):
                        yield sub

        prs = Presentation(path)
        pages: List[Tuple[int, str]] = []
        total_ocr_imgs = 0

        for slide_no, slide in enumerate(prs.slides, start=1):
            slide_lines: List[str] = []
            slide_img_idx = 0

            for shape in iter_all_shapes(slide.shapes):
                # 일반 텍스트 프레임 (취소선 run 제외)
                if getattr(shape, "has_text_frame", False):
                    tf = shape.text_frame
                    for para in tf.paragraphs:
                        text = "".join(
                            run.text for run in para.runs
                            if not getattr(run.font, 'strikethrough', False)
                        )
                        text = _clean_common_noise(_normalize_unicode(_strip_null_chars(text))).strip()
                        if text and not _is_formula_or_noise(text):
                            slide_lines.append(text)

                # 표 처리 (구조화, 취소선 제외)
                if getattr(shape, "has_table", False):
                    table = shape.table
                    table_rows = []
                    for row in table.rows:
                        cell_texts = []
                        for cell in row.cells:
                            # 셀 내 취소선 run 제외
                            cell_parts = []
                            if hasattr(cell, 'text_frame'):
                                for para in cell.text_frame.paragraphs:
                                    for run in para.runs:
                                        if not getattr(run.font, 'strikethrough', False):
                                            cell_parts.append(run.text)
                            cell_text = _clean_common_noise(_normalize_unicode(_strip_null_chars(''.join(cell_parts)))).strip()
                            if not cell_text:
                                # fallback: text_frame 없는 경우
                                cell_text = _clean_common_noise(_normalize_unicode(_strip_null_chars(cell.text))).strip()
                            if cell_text and not _is_formula_or_noise(cell_text):
                                cell_texts.append(cell_text)

                        if cell_texts:
                            table_rows.append(" | ".join(cell_texts))

                    if table_rows:
                        slide_lines.append("\n".join(table_rows))

                # 이미지 OCR (ocr_client가 있을 때만)
                if ocr_client is not None and getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                    try:
                        image = shape.image
                        img_bytes = image.blob
                        mime = image.content_type or "image/png"
                        slide_img_idx += 1
                        ocr_text = _ocr_image_bytes_safe(
                            ocr_client, img_bytes, mime,
                            upscale_threshold_px=image_upscale_threshold_px,
                            upscale_factor=image_upscale_factor,
                            context_label=f"PPTX slide {slide_no} img {slide_img_idx}",
                        )
                        if ocr_text:
                            slide_lines.append(ocr_text)
                            total_ocr_imgs += 1
                    except Exception as e:
                        logger.warning("PPTX slide %d 이미지 추출 실패: %s", slide_no, e)

            if slide_lines:
                combined = "\n".join(slide_lines)
                combined = _postprocess_pdf_text(combined)
                pages.append((slide_no, combined))

        if ocr_client is not None:
            logger.info("PPTX OCR 적용: %s (이미지 %d개 처리)", path, total_ocr_imgs)

        return pages
    except Exception as e:
        logger.error(f"PPTX 추출 실패: {path}, 에러: {e}")
        raise








def _extract_html_paragraphs(path: str) -> Tuple[List[HwpxParagraph], int]:
    """HTML 파일에서 문단 목록 추출 (한글 '웹 문서로 저장' 대응)

    .hwp 확장자이지만 실제로는 HTML인 파일을 처리한다.
    표준 라이브러리 html.parser를 사용하여 외부 의존성 없음.

    Returns:
        (paragraphs, total_sections) — 단일 섹션(section_idx=0)으로 반환
    """
    from html.parser import HTMLParser

    with open(path, 'rb') as f:
        raw = f.read()

    # 인코딩 감지: meta charset 또는 기본 euc-kr (한글 HTML에서 흔함)
    encoding = 'utf-8'
    head = raw[:2048].decode('ascii', errors='ignore').lower()
    import re as _re
    m = _re.search(r'charset=["\']?([^"\'\s;>]+)', head)
    if m:
        encoding = m.group(1)
    try:
        html_text = raw.decode(encoding, errors='ignore')
    except (LookupError, UnicodeDecodeError):
        html_text = raw.decode('euc-kr', errors='ignore')

    # HTML 파싱: 태그 제거 후 텍스트만 수집
    # script/style만 쌍(start+end)으로 skip, head는 별도 플래그 처리
    _SKIP_PAIR_TAGS = {'script', 'style'}

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.texts: List[str] = []
            self._skip_depth = 0
            self._in_head = False

        def handle_starttag(self, tag, attrs):
            t = tag.lower()
            if t == 'head':
                self._in_head = True
            elif t in _SKIP_PAIR_TAGS:
                self._skip_depth += 1

        def handle_endtag(self, tag):
            t = tag.lower()
            if t == 'head':
                self._in_head = False
            elif t in _SKIP_PAIR_TAGS and self._skip_depth > 0:
                self._skip_depth -= 1

        def handle_data(self, data):
            if self._in_head or self._skip_depth > 0:
                return
            text = data.strip()
            if text:
                self.texts.append(text)

    parser = _TextExtractor()
    parser.feed(html_text)

    paragraphs: List[HwpxParagraph] = []
    section_paras = []
    for text in parser.texts:
        text = _clean_common_noise(_normalize_unicode(_strip_null_chars(text))).strip()
        if text and not _is_formula_or_noise(text):
            section_paras.append(text)

    section_para_count = len(section_paras)
    for i, text in enumerate(section_paras):
        relative_pos = i / section_para_count if section_para_count > 1 else 0.5
        paragraphs.append(HwpxParagraph(
            para_idx=i,
            text=text,
            section_idx=0,
            relative_position=relative_pos
        ))

    return paragraphs, 1 if paragraphs else 0


def _extract_hwpml_paragraphs(path: str) -> Tuple[List[HwpxParagraph], int]:
    """HWPML(plain XML) 파일에서 문단 목록 추출

    HWPML은 한글의 XML 내보내기 포맷으로, 확장자가 .hwp인 경우도 있음.
    구조: HWPML > BODY > SECTION > P > TEXT > CHAR

    Returns:
        (paragraphs, total_sections)
    """
    from xml.etree import ElementTree as ET

    with open(path, 'rb') as f:
        raw = f.read()

    # 인코딩 감지: XML 선언에서 encoding 속성 확인, 없으면 utf-8
    encoding = 'utf-8'
    try:
        head = raw[:200].decode('ascii', errors='ignore')
        import re as _re
        m = _re.search(r'encoding=["\']([^"\']+)["\']', head)
        if m:
            encoding = m.group(1)
    except Exception:
        pass

    xml_text = raw.decode(encoding, errors='ignore')
    root = ET.fromstring(xml_text)

    # HWPML 태그는 대문자, 네임스페이스 없음
    # 루트가 HWPML인지 확인
    root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    if root_tag.upper() != 'HWPML':
        raise ValueError(f"HWPML 루트 태그가 아닙니다: {root_tag}")

    paragraphs: List[HwpxParagraph] = []
    para_idx = 0
    section_idx = 0

    # BODY > SECTION 탐색
    for body in root:
        body_tag = body.tag.split('}')[-1] if '}' in body.tag else body.tag
        if body_tag.upper() != 'BODY':
            continue
        for section in body:
            section_tag = section.tag.split('}')[-1] if '}' in section.tag else section.tag
            if section_tag.upper() != 'SECTION':
                continue

            section_paras: List[str] = []

            def _collect_text_from_p(p_elem):
                """P 요소에서 CHAR 텍스트를 수집"""
                texts = []
                for elem in p_elem.iter():
                    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    if tag.upper() == 'CHAR' and elem.text:
                        t = elem.text.strip()
                        if t:
                            texts.append(t)
                    # T 태그도 체크 (일부 HWPML 변형)
                    elif tag.upper() == 'T' and elem.text:
                        t = elem.text.strip()
                        if t:
                            texts.append(t)
                return ' '.join(texts)

            def _walk_hwpml(elem):
                """재귀적으로 P 요소를 찾아 텍스트 수집"""
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag.upper() == 'P':
                    text = _collect_text_from_p(elem)
                    text = _clean_common_noise(_normalize_unicode(_strip_null_chars(text))).strip()
                    if text and not _is_formula_or_noise(text):
                        section_paras.append(text)
                    # P 내부 중첩 구조 (표 안 텍스트 등)도 탐색
                    for child in elem:
                        _walk_hwpml(child)
                    return
                for child in elem:
                    _walk_hwpml(child)

            _walk_hwpml(section)

            section_para_count = len(section_paras)
            for i, text in enumerate(section_paras):
                relative_pos = i / section_para_count if section_para_count > 1 else 0.5
                paragraphs.append(HwpxParagraph(
                    para_idx=para_idx,
                    text=text,
                    section_idx=section_idx,
                    relative_position=relative_pos
                ))
                para_idx += 1

            section_idx += 1

    return paragraphs, section_idx


def _extract_hwp_paragraphs(path: str) -> Tuple[List[HwpxParagraph], int]:
    """HWP 파일에서 문단 목록 추출 (gethwp 사용)
    
    Returns:
        (paragraphs, total_sections)
    """
    if gethwp is None:
        raise ImportError(
            "gethwp 모듈이 설치되지 않았습니다. HWP 파일 처리를 위해 다음 명령어로 설치하세요:\n"
            "pip install gethwp"
        )
    
    from gethwp import OleFileIO
    
    paragraphs: List[HwpxParagraph] = []
    para_idx = 0
    section_idx = 0
    
    with OleFileIO(path) as ole:
        gethwp.validate_hwp_file(ole)
        compression_flag = gethwp.get_compression_flag(ole)
        section_ids = gethwp.get_section_ids(ole)
        
        for section_id in section_ids:
            text = gethwp.read_section(ole, section_id, compression_flag)
            text = _remove_garbled_cjk(_normalize_unicode(_strip_null_chars(text)))
            text = _clean_common_noise(text)

            if not text or not text.strip():
                section_idx += 1
                continue

            # 섹션 텍스트를 줄바꿈으로 분리하여 문단 생성
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            section_para_count = len(lines)
            for i, line in enumerate(lines):
                relative_pos = i / section_para_count if section_para_count > 1 else 0.5
                paragraphs.append(HwpxParagraph(
                    para_idx=para_idx,
                    text=line,
                    section_idx=section_idx,
                    relative_position=relative_pos
                ))
                para_idx += 1
            
            section_idx += 1
    
    return paragraphs, section_idx


def extract_hwp_pages(
    path: str,
    use_pyhwpx: bool = False,
    use_libreoffice: bool = False,
    ocr_client=None,
    image_upscale_threshold_px: int = 800,
    image_upscale_factor: float = 2.0,
) -> Tuple[List[Tuple[int, str]], str]:
    """HWP → (page_no, text) 리스트 + locator_type (페이지 추정 포함)

    Args:
        path: HWP 파일 경로
        use_pyhwpx: (deprecated) 더 이상 사용하지 않음
        use_libreoffice: (deprecated) 더 이상 사용하지 않음
        ocr_client: OCR 클라이언트. 있으면 OLE BinData/ 스트림의 이미지를 OCR해 별도 섹션으로 추가.

    Returns:
        (pages, locator_type)
        - pages: [(page_no_or_section, text), ...]
        - locator_type: "page_estimated" 또는 "section"
    """
    # pyhwpx 사용 요청 시 경고
    if use_pyhwpx and PYHWPX_AVAILABLE:
        logger.warning("HWP에서 pyhwpx 사용은 더 이상 권장하지 않습니다. gethwp 파싱을 사용합니다.")

    # LibreOffice 사용 요청 시 경고
    if use_libreoffice:
        logger.warning("HWP에서 LibreOffice PDF 변환은 더 이상 사용하지 않습니다. gethwp 파싱을 사용합니다.")

    # gethwp로 문단 추출
    try:
        logger.info("HWP 추출 시작: %s", path)

        # OCR 활성화 시 BinData 이미지 추출 (OLE 메인 경로에서만 유효)
        ocr_texts: List[str] = []
        if ocr_client is not None:
            ocr_texts = _ocr_hwp_bindata(
                path,
                ocr_client=ocr_client,
                upscale_threshold_px=image_upscale_threshold_px,
                upscale_factor=image_upscale_factor,
            )

        paragraphs, total_sections = _extract_hwp_paragraphs(path)

        if not paragraphs:
            logger.warning("HWP에서 문단을 추출하지 못했습니다: %s", path)
            return (_append_hwp_ocr_section([], ocr_texts, "HWP"), "section")
        
        logger.info("HWP 문단 추출 완료: %s (총 %d개 문단, %d개 섹션)", path, len(paragraphs), total_sections)
        
        # 페이지 anchor 구축 (보수적)
        anchors, anchor_stats = _build_page_anchors(paragraphs, score_threshold=0.6)
        
        # 상세 로그
        logger.info(
            "HWP 페이지 anchor 분석: raw_candidates=%d, excluded=%d, initial=%d, final=%d, plausible_max=%d",
            anchor_stats.get("raw_candidates", 0),
            anchor_stats.get("excluded_candidates", 0),
            anchor_stats.get("initial_anchors", 0),
            anchor_stats.get("final_anchors", 0),
            anchor_stats.get("plausible_max_page", 0)
        )
        
        # 페이지 할당
        page_assignments = _assign_estimated_pages(paragraphs, anchors)
        
        # 섹션별로 텍스트 그룹화 (section fallback용)
        section_texts: Dict[int, List[str]] = {}
        # 페이지별로 텍스트 그룹화 (page_estimated용)
        page_texts: Dict[int, List[str]] = {}
        
        for para_idx, page_no, locator_type, confidence, source in page_assignments:
            para = next((p for p in paragraphs if p.para_idx == para_idx), None)
            if para:
                if locator_type == "section":
                    # section fallback: section_idx 기반
                    if page_no not in section_texts:
                        section_texts[page_no] = []
                    section_texts[page_no].append(para.text)
                else:
                    # page_estimated: page_no 기반
                    if page_no not in page_texts:
                        page_texts[page_no] = []
                    page_texts[page_no].append(para.text)
        
        # 통계 로그
        page_estimated_count = sum(1 for _, _, lt, _, _ in page_assignments if lt == "page_estimated")
        section_fallback_count = sum(1 for _, _, lt, _, _ in page_assignments if lt == "section")
        
        logger.info(
            "HWP 추출 완료: %s (섹션 %d개, page_estimated: %d문단, section: %d문단)",
            path, total_sections, page_estimated_count, section_fallback_count
        )
        
        # locator_type 결정
        if page_estimated_count > 0:
            # page_estimated가 있으면 page_estimated 사용
            result: List[Tuple[int, str]] = []
            for page_no in sorted(page_texts.keys()):
                combined_text = "\n".join(page_texts[page_no])
                result.append((page_no, combined_text))
            return (_append_hwp_ocr_section(result, ocr_texts, "HWP"), "page_estimated")
        else:
            # page_estimated가 없으면 section fallback
            result: List[Tuple[int, str]] = []
            for section_idx in sorted(section_texts.keys()):
                combined_text = "\n".join(section_texts[section_idx])
                result.append((section_idx, combined_text))
            return (_append_hwp_ocr_section(result, ocr_texts, "HWP"), "section")

    except OSError as e:
        if "not an OLE2 structured storage file" not in str(e):
            logger.error(f"HWP 추출 실패: {path}, 에러: {e}")
            raise

        # OLE2가 아닌 파일 — 실제 포맷 감지 후 폴백
        try:
            with open(path, 'rb') as f:
                magic_bytes = f.read(16)
        except Exception:
            magic_bytes = b''

        # 1) XML(HWPML) 감지: <?xml 로 시작
        if magic_bytes.lstrip(b'\xef\xbb\xbf').startswith(b'<?xml') or magic_bytes.lstrip(b'\xef\xbb\xbf').startswith(b'<HWPML'):
            logger.warning("HWP 파일이 HWPML(XML) 포맷으로 감지됨, HWPML 추출로 폴백: %s", path)
            try:
                paragraphs, total_sections = _extract_hwpml_paragraphs(path)
                if paragraphs:
                    logger.info("HWPML 문단 추출 완료: %s (총 %d개 문단, %d개 섹션)", path, len(paragraphs), total_sections)
                    anchors, anchor_stats = _build_page_anchors(paragraphs, score_threshold=0.6)
                    page_assignments = _assign_estimated_pages(paragraphs, anchors)
                    section_texts: Dict[int, List[str]] = {}
                    page_texts: Dict[int, List[str]] = {}
                    for para_idx_val, page_no, locator_type, confidence, source in page_assignments:
                        para = next((p for p in paragraphs if p.para_idx == para_idx_val), None)
                        if para:
                            if locator_type == "section":
                                section_texts.setdefault(page_no, []).append(para.text)
                            else:
                                page_texts.setdefault(page_no, []).append(para.text)
                    if page_texts:
                        result: List[Tuple[int, str]] = []
                        for pg in sorted(page_texts.keys()):
                            result.append((pg, "\n".join(page_texts[pg])))
                        return (result, "page_estimated")
                    else:
                        result: List[Tuple[int, str]] = []
                        for si in sorted(section_texts.keys()):
                            result.append((si, "\n".join(section_texts[si])))
                        return (result, "section")
                logger.warning("HWPML에서 문단을 추출하지 못했습니다: %s", path)
            except Exception as hwpml_err:
                logger.warning("HWPML 추출 실패, HWPX 폴백 시도: %s, 에러: %s", path, hwpml_err)

        # 2) HTML 감지: <HTML, <!DOCTYPE 등
        stripped_magic = magic_bytes.lstrip(b'\xef\xbb\xbf').upper()
        if stripped_magic.startswith(b'<HTML') or stripped_magic.startswith(b'<!DOC'):
            logger.warning("HWP 파일이 HTML 포맷으로 감지됨, HTML 추출로 폴백: %s", path)
            try:
                paragraphs, total_sections = _extract_html_paragraphs(path)
                if paragraphs:
                    logger.info("HTML 문단 추출 완료: %s (총 %d개 문단)", path, len(paragraphs))
                    result: List[Tuple[int, str]] = []
                    section_texts_html: Dict[int, List[str]] = {}
                    for para in paragraphs:
                        section_texts_html.setdefault(para.section_idx, []).append(para.text)
                    for si in sorted(section_texts_html.keys()):
                        result.append((si, "\n".join(section_texts_html[si])))
                    return (result, "section")
                logger.warning("HTML에서 문단을 추출하지 못했습니다: %s", path)
            except Exception as html_err:
                logger.warning("HTML 추출 실패: %s, 에러: %s", path, html_err)

        # 3) ZIP(HWPX) 폴백
        logger.warning("HWP 파일이 OLE2가 아닌 포맷으로 감지됨, HWPX 추출로 폴백: %s", path)
        try:
            return extract_hwpx_pages(
                path,
                ocr_client=ocr_client,
                image_upscale_threshold_px=image_upscale_threshold_px,
                image_upscale_factor=image_upscale_factor,
            )
        except Exception as hwpx_err:
            raise ValueError(
                f"HWP 파일이 OLE2/HWPML/HTML/HWPX 어느 포맷에도 해당하지 않습니다 (매직바이트: {magic_bytes[:16].hex()}). "
                f"파일이 손상되었거나 지원하지 않는 포맷일 수 있습니다: {path}"
            ) from hwpx_err
    except Exception as e:
        logger.error(f"HWP 추출 실패: {path}, 에러: {e}")
        raise


def extract_hwp_text(path: str) -> str:
    """HWP → 전체 텍스트 (하위 호환성)"""
    if gethwp is None:
        raise ImportError(
            "gethwp 모듈이 설치되지 않았습니다. HWP 파일 처리를 위해 다음 명령어로 설치하세요:\n"
            "pip install gethwp"
        )
    
    try:
        text = gethwp.read_hwp(path)
        text = _strip_null_chars(text)
        return text or ""
    except Exception as e:
        logger.error(f"HWP 추출 실패: {path}, 에러: {e}")
        raise




def _extract_hwpx_paragraphs(
    path: str,
    ocr_client=None,
    image_upscale_threshold_px: int = 800,
    image_upscale_factor: float = 2.0,
) -> Tuple[List[HwpxParagraph], int]:
    """HWPX 파일에서 문단 목록 추출

    재귀적으로 XML 트리를 순회하며:
    - 표(tbl), 필드(fieldBegin~fieldEnd) 등 하위는 건너뜀
    - 문단(p) 단위로 텍스트 런(t)을 수집하여 하나의 문단 텍스트로 결합
    - ocr_client가 주어지면 <hp:pic> 요소를 만날 때 BinData 이미지를 OCR해
      해당 위치(paragraph 흐름 안)에 OCR 텍스트를 inline으로 삽입

    Returns:
        (paragraphs, total_sections)
    """
    import io
    import zipfile
    from xml.etree import ElementTree as ET

    # 건너뛸 태그 (하위 요소 전체 무시)
    # hyperlink: 하이퍼링크 메타데이터 (TARGET_BOOKMARK, OBJECT_TYPE_PAGE 등)
    # bookmark: 북마크 참조 정보
    _SKIP_TAGS = {'tbl', 'table', 'pic', 'img', 'drawingobject',
                  'fieldbegin', 'fieldend', 'ctrl', 'switch', 'equation',
                  'hyperlink', 'bookmark'}

    # _walk_section용: tbl/table은 내부 텍스트 추출을 위해 재귀 허용
    # ocr_client가 있으면 pic/img/drawingobject를 처리(OCR)해야 하므로 skip 대상에서 제외
    if ocr_client is not None:
        _SKIP_TAGS_SECTION = {'fieldbegin', 'fieldend', 'ctrl', 'switch', 'equation',
                              'hyperlink', 'bookmark'}
    else:
        _SKIP_TAGS_SECTION = {'pic', 'img', 'drawingobject',
                              'fieldbegin', 'fieldend', 'ctrl', 'switch', 'equation',
                              'hyperlink', 'bookmark'}

    def _get_local_tag(elem) -> str:
        """네임스페이스 제거 후 소문자 태그명 반환"""
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        return tag.lower()

    def _collect_paragraph_texts(p_elem) -> str:
        """문단(p) 요소 내부에서 텍스트 런(t)만 수집하여 결합

        <p> 안의 <run> > <t> 구조를 따라가며 텍스트를 모음.
        필드코드, 이미지, 표 등은 건너뜀.
        취소선이 적용된 run은 건너뜀.
        """
        texts = []

        def _walk(elem):
            tag = _get_local_tag(elem)

            # 건너뛸 태그면 하위 전체 무시
            if tag in _SKIP_TAGS:
                return

            # run 요소: 취소선 여부 확인
            if tag == 'run':
                char_pr_id = elem.get('charPrIDRef')
                if char_pr_id and char_pr_id in strikethrough_char_ids:
                    return  # 취소선 run 전체 건너뜀

            # 텍스트 요소면 수집
            if tag == 't' and elem.text:
                t = elem.text.strip()
                if t:
                    texts.append(t)

            # 자식 요소 재귀 순회
            for child in elem:
                _walk(child)

        _walk(p_elem)
        return ' '.join(texts)

    # 처리한 binaryItemIDRef 추적 (같은 이미지가 여러 paragraph에서 참조될 때 중복 OCR 방지)
    ocr_cache: Dict[str, str] = {}

    def _ocr_pic_inline(pic_elem) -> Optional[str]:
        """<hp:pic> 요소에서 binaryItemIDRef 추출 → BinData 이미지 OCR → 텍스트 반환.

        ocr_client가 None이면 호출되지 않음 (호출부에서 보장).
        실패 또는 결과 빈 문자열이면 None 반환.
        """
        # pic 자손 중 binaryItemIDRef 속성을 가진 요소(보통 <hc:img>) 찾기
        bin_ref = None
        for child in pic_elem.iter():
            ref = child.get('binaryItemIDRef')
            if ref:
                bin_ref = ref
                break
        if not bin_ref:
            return None

        # 이미 OCR 처리한 ID면 캐시 사용
        if bin_ref in ocr_cache:
            return ocr_cache[bin_ref] or None

        bin_entry = binary_data_map.get(bin_ref)
        if not bin_entry:
            logger.debug("HWPX inline OCR: binaryItemIDRef=%s 에 해당하는 BinData 파일 없음", bin_ref)
            ocr_cache[bin_ref] = ""
            return None

        img_bytes, mime = bin_entry
        ocr_text = _ocr_image_bytes_safe(
            ocr_client, img_bytes, mime,
            upscale_threshold_px=image_upscale_threshold_px,
            upscale_factor=image_upscale_factor,
            context_label=f"HWPX inline {bin_ref}",
        )
        ocr_cache[bin_ref] = ocr_text or ""
        return ocr_text or None

    def _walk_section(elem, section_paras, para_idx_ref):
        """섹션 XML을 재귀 순회하며 문단 텍스트 수집

        문단(p) 요소를 만나면 _collect_paragraph_texts로 텍스트 추출.
        ocr_client가 있을 때 <hp:pic> 요소를 만나면 inline으로 OCR 호출해 paragraph로 삽입.
        표(tbl)는 내부 sublist > p 구조에 텍스트가 있을 수 있으므로 재귀 탐색.
        """
        tag = _get_local_tag(elem)

        # 건너뛸 태그 (하위 전체 무시) — tbl/table은 제외 (내부 재귀 필요)
        if tag in _SKIP_TAGS_SECTION:
            return

        # 이미지 요소 (pic): ocr_client가 있을 때만 처리 (없으면 _SKIP_TAGS_SECTION에 포함됨)
        if tag == 'pic' and ocr_client is not None:
            ocr_text = _ocr_pic_inline(elem)
            if ocr_text:
                cleaned = _clean_common_noise(_normalize_unicode(_strip_null_chars(ocr_text))).strip()
                if cleaned:
                    section_paras.append((para_idx_ref[0], cleaned))
                    para_idx_ref[0] += 1
            return  # pic 하위는 더 들어가지 않음 (이미지 메타만 있음)

        # img/drawingobject 등 다른 이미지 표현도 ocr_client가 있을 때만 처리
        if tag in ('img', 'drawingobject') and ocr_client is not None:
            # 이 자신이 binaryItemIDRef를 가질 수도 있고, 자식에서 가질 수도 있어 동일 헬퍼 호출
            ocr_text = _ocr_pic_inline(elem)
            if ocr_text:
                cleaned = _clean_common_noise(_normalize_unicode(_strip_null_chars(ocr_text))).strip()
                if cleaned:
                    section_paras.append((para_idx_ref[0], cleaned))
                    para_idx_ref[0] += 1
            return

        # 문단 요소 발견: 텍스트 수집
        if tag == 'p':
            text = _collect_paragraph_texts(elem)
            text = _clean_common_noise(_normalize_unicode(_strip_null_chars(text))).strip()
            if text and not _is_formula_or_noise(text):
                section_paras.append((para_idx_ref[0], text))
                para_idx_ref[0] += 1
            # p 내부의 표(tbl) 안에 있는 텍스트와 이미지(pic)도 자식 순회로 처리
            # (레이아웃 표: sec > p > run > tbl > tr > tc > sublist > p > run > t)
            # 이미지: sec > p > run > pic
            for child in elem:
                _walk_section(child, section_paras, para_idx_ref)
            return

        # 그 외 컨테이너 요소 (tbl, tr, tc, sublist 등): 자식 순회
        for child in elem:
            _walk_section(child, section_paras, para_idx_ref)

    paragraphs: List[HwpxParagraph] = []
    section_idx = 0
    strikethrough_char_ids: set = set()  # 취소선이 적용된 charShape ID 집합
    # binaryItemIDRef → (bytes, mime) 매핑.
    # HWPX 표준: <hc:img binaryItemIDRef="image1"/> → BinData/image1.<ext>
    # ocr_client가 있을 때만 build (불필요한 메모리 사용 방지).
    binary_data_map: Dict[str, Tuple[bytes, str]] = {}

    with open(path, 'rb') as f:
        hwpx_file_bytes = f.read()

    with io.BytesIO(hwpx_file_bytes) as bytes_io:
        with zipfile.ZipFile(bytes_io, 'r') as zip_ref:
            # BinData/ 폴더 파일들을 binaryItemIDRef → (bytes, mime)로 미리 매핑
            if ocr_client is not None:
                for name in zip_ref.namelist():
                    if not name.startswith('BinData/') or name.endswith('/'):
                        continue
                    base = os.path.basename(name)
                    # "image1.bmp" → ID "image1"
                    bin_id = os.path.splitext(base)[0]
                    ext = os.path.splitext(base)[1].lower()
                    mime = _XLSX_MEDIA_MIME.get(ext)
                    if not mime:
                        continue  # 비-이미지 파일 스킵
                    try:
                        data = zip_ref.read(name)
                    except Exception as e:
                        logger.warning("HWPX BinData 읽기 실패 (%s): %s", name, e)
                        continue
                    binary_data_map[bin_id] = (data, mime)
                logger.info("HWPX BinData 매핑 build 완료: %d개", len(binary_data_map))

            # header.xml에서 취소선 charShape ID 수집
            if 'Contents/header.xml' in zip_ref.namelist():
                try:
                    header_content = zip_ref.read('Contents/header.xml').decode('utf-8', errors='ignore')
                    header_tree = ET.fromstring(header_content)
                    for elem in header_tree.iter():
                        local_tag = _get_local_tag(elem)
                        if local_tag == 'charshape':
                            shape_id = elem.get('id')
                            if shape_id:
                                for child in elem.iter():
                                    if _get_local_tag(child) == 'strikeout':
                                        shape_val = child.get('shape', 'NONE')
                                        if shape_val != 'NONE':
                                            strikethrough_char_ids.add(shape_id)
                                        break
                    if strikethrough_char_ids:
                        logger.debug("HWPX 취소선 charShape IDs: %s", strikethrough_char_ids)
                except Exception as e:
                    logger.debug(f"HWPX header.xml 파싱 실패 (취소선 무시): {e}")

            xml_files = [
                f for f in zip_ref.infolist()
                if f.filename.startswith('Contents/') and f.filename.endswith('.xml')
            ]
            # 자연 정렬: section0, section1, section2, ..., section10 순서 보장
            # (문자열 정렬 시 section10이 section2보다 앞에 오는 문제 방지)
            xml_files.sort(key=lambda x: [
                int(c) if c.isdigit() else c.lower()
                for c in re.split(r'(\d+)', x.filename)
            ])

            para_idx_ref = [0]  # 뮤터블 카운터

            for file_info in xml_files:
                with zip_ref.open(file_info) as file:
                    try:
                        tree = ET.parse(file)
                        root = tree.getroot()

                        # 섹션 내 모든 문단 수집
                        section_paras = []
                        _walk_section(root, section_paras, para_idx_ref)

                        # 섹션 내 상대 위치 계산
                        section_para_count = len(section_paras)
                        for i, (p_idx, text) in enumerate(section_paras):
                            relative_pos = i / section_para_count if section_para_count > 1 else 0.5
                            paragraphs.append(HwpxParagraph(
                                para_idx=p_idx,
                                text=text,
                                section_idx=section_idx,
                                relative_position=relative_pos
                            ))

                        section_idx += 1

                    except Exception as xml_err:
                        logger.warning("HWPX XML 파싱 실패: %s, 에러: %s", file_info.filename, xml_err)
                        continue

    return paragraphs, section_idx


def _detect_image_magic(data: bytes) -> Optional[str]:
    """이미지 매직바이트로 mime 판정 (PNG/JPEG/GIF/BMP/WEBP/TIFF). 매치 안 되면 None."""
    if not data or len(data) < 4:
        return None
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    if data.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return "image/gif"
    if data.startswith(b'BM'):
        return "image/bmp"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    if data.startswith(b'II*\x00') or data.startswith(b'MM\x00*'):
        return "image/tiff"
    return None


def _ocr_hwp_bindata(
    path: str,
    ocr_client,
    upscale_threshold_px: int = 800,
    upscale_factor: float = 2.0,
) -> List[str]:
    """HWP(OLE) 파일의 BinData/ 스트림들에서 이미지를 추출해 OCR.

    HWP의 BinData stream은 raw bytes일 수도 있고 zlib raw deflate로 압축되어 있을 수도 있으므로,
    두 경우 모두 시도해 이미지 매직바이트가 검출되면 OCR 호출.
    """
    if gethwp is None:
        logger.debug("HWP OCR 스킵: gethwp 미설치")
        return []

    import zlib

    results: List[str] = []
    try:
        from gethwp import OleFileIO
        with OleFileIO(path) as ole:
            bin_entries = [e for e in ole.listdir() if len(e) >= 2 and e[0] == 'BinData']
            if not bin_entries:
                logger.debug("HWP OCR: BinData 항목 없음")
                return results

            for idx, entry in enumerate(bin_entries, start=1):
                entry_name = '/'.join(entry)
                try:
                    raw = ole.openstream(entry).read()
                except Exception as e:
                    logger.warning("HWP BinData 스트림 읽기 실패 (%s): %s", entry_name, e)
                    continue

                # 1) raw 그대로 이미지 매직바이트 검사
                mime = _detect_image_magic(raw)
                img_bytes = raw if mime else None

                # 2) 안되면 raw deflate(-15) 디컴프레스 후 재검사
                if not mime:
                    try:
                        decompressed = zlib.decompress(raw, -15)
                        mime = _detect_image_magic(decompressed)
                        if mime:
                            img_bytes = decompressed
                    except zlib.error:
                        pass

                if not mime or not img_bytes:
                    logger.debug("HWP BinData 비-이미지 스킵: %s", entry_name)
                    continue

                ocr_text = _ocr_image_bytes_safe(
                    ocr_client, img_bytes, mime,
                    upscale_threshold_px=upscale_threshold_px,
                    upscale_factor=upscale_factor,
                    context_label=f"HWP img {idx}/{len(bin_entries)} ({entry_name})",
                )
                if ocr_text:
                    results.append(ocr_text)
    except Exception as e:
        logger.warning("HWP BinData OCR 전체 실패: %s", e)

    return results


def _interleave_hwp_ocr_inline(
    pages: List[Tuple[int, str]],
    ocr_texts: List[str],
    context_label: str = "HWP",
) -> List[Tuple[int, str]]:
    """HWP OCR 텍스트를 본문 paragraph 사이에 균등 분산해 inline 삽입.

    HWP(OLE)는 텍스트 흐름 안의 정확한 이미지 위치를 파악하기 어려워서,
    OCR 텍스트들을 본문 길이에 비례해 균등하게 분산 삽입한다.
    줄바꿈 경계로 위치를 보정해 문장 중간이 잘리지 않게 한다.
    이렇게 하면 본문+OCR이 청크에 자연스럽게 섞여 검색 시 컨텍스트 단절을 줄인다.
    """
    if not ocr_texts:
        return pages

    cleaned: List[str] = []
    for t in ocr_texts:
        c = _clean_common_noise(_normalize_unicode(_strip_null_chars(t))).strip()
        if c:
            cleaned.append(c)
    if not cleaned:
        return pages

    total_chars = sum(len(t) for _, t in pages)
    if total_chars == 0:
        # 본문이 비었으면 OCR을 단일 섹션으로 추가
        logger.info("%s OCR inline: 본문 0자, OCR %d개를 단일 섹션으로 추가", context_label, len(cleaned))
        return [(1, "\n\n".join(cleaned))]

    n_ocr = len(cleaned)
    # 본문 전체에서 OCR을 균등 분배할 위치 (1/(n+1), 2/(n+1), ...)
    insertion_points = [int(total_chars * (i + 1) / (n_ocr + 1)) for i in range(n_ocr)]

    result: List[Tuple[int, str]] = []
    char_cursor = 0
    ocr_cursor = 0

    for page_no, text in pages:
        page_start = char_cursor
        page_end = char_cursor + len(text)

        # 이 페이지 본문 안에 들어갈 OCR 분배 지점들 (현재 페이지 범위에 속하는 것만)
        local_insertions: List[Tuple[int, str]] = []
        while ocr_cursor < n_ocr and insertion_points[ocr_cursor] < page_end:
            local_pos = max(0, insertion_points[ocr_cursor] - page_start)
            local_insertions.append((local_pos, cleaned[ocr_cursor]))
            ocr_cursor += 1

        if not local_insertions:
            result.append((page_no, text))
        else:
            new_text = text
            offset = 0
            for local_pos, ocr_text in local_insertions:
                pos = local_pos + offset
                # 다음 줄바꿈을 찾아 그 자리에 삽입 (문장 중간이 잘리지 않도록)
                nl = new_text.find('\n', pos)
                actual = (nl + 1) if nl != -1 else len(new_text)
                inserted = ocr_text + "\n"
                new_text = new_text[:actual] + inserted + new_text[actual:]
                offset += len(inserted)
            result.append((page_no, new_text))

        char_cursor = page_end

    # 본문 끝났는데 남은 OCR이 있으면 마지막 페이지/섹션 텍스트 끝에 추가
    if ocr_cursor < n_ocr:
        leftover = "\n\n".join(cleaned[ocr_cursor:])
        if result:
            last_no, last_text = result[-1]
            result[-1] = (last_no, last_text + "\n" + leftover)
        else:
            result.append((1, leftover))

    logger.info(
        "%s OCR inline: 본문 %d자에 OCR %d개 균등 분산 삽입 (페이지/섹션 %d개)",
        context_label, total_chars, n_ocr, len(result),
    )
    return result


# 기존 호출 호환용 alias (HWP가 사용)
_append_hwp_ocr_section = _interleave_hwp_ocr_inline


def extract_hwpx_pages(
    path: str,
    use_pyhwpx: bool = False,
    use_libreoffice: bool = False,
    ocr_client=None,
    image_upscale_threshold_px: int = 800,
    image_upscale_factor: float = 2.0,
) -> Tuple[List[Tuple[int, str]], str]:
    """HWPX → (page_no, text) 리스트 + locator_type (페이지 추정 포함, 보수적)

    Args:
        path: HWPX 파일 경로
        use_pyhwpx: (deprecated) 더 이상 사용하지 않음
        use_libreoffice: (deprecated) 더 이상 사용하지 않음
        ocr_client: OCR 클라이언트. 있으면 BinData/ 폴더의 이미지를 OCR해 별도 섹션으로 추가.

    Returns:
        (pages, locator_type)
        - pages: [(page_no_or_section, text), ...]
        - locator_type: "page_estimated" 또는 "section"
    """
    # pyhwpx 사용 요청 시 경고
    if use_pyhwpx and PYHWPX_AVAILABLE:
        logger.warning("HWPX에서 pyhwpx 사용은 더 이상 권장하지 않습니다. XML 파싱을 사용합니다.")
    
    # LibreOffice 사용 요청 시 경고
    if use_libreoffice:
        logger.warning("HWPX에서 LibreOffice PDF 변환은 더 이상 사용하지 않습니다. XML 파싱을 사용합니다.")
    
    # XML 파싱으로 문단 추출 (ocr_client가 있으면 inline으로 OCR도 함께 수행)
    try:
        logger.info("HWPX 추출 시작: %s (ocr=%s)", path, ocr_client is not None)

        paragraphs, total_sections = _extract_hwpx_paragraphs(
            path,
            ocr_client=ocr_client,
            image_upscale_threshold_px=image_upscale_threshold_px,
            image_upscale_factor=image_upscale_factor,
        )

        if not paragraphs:
            logger.warning("HWPX에서 문단을 추출하지 못했습니다: %s", path)

            # gethwp fallback (OCR은 inline으로 안 들어가지만 본문 텍스트라도 살림)
            if gethwp is not None:
                text = gethwp.read_hwpx(path)
                text = _clean_common_noise(_normalize_unicode(_strip_null_chars(text)))
                if text:
                    logger.info("HWPX 추출 완료 (gethwp fallback): %s", path)
                    return ([(1, text)], "section")

            return ([], "section")
        
        logger.info("HWPX 문단 추출 완료: %s (총 %d개 문단, %d개 섹션)", path, len(paragraphs), total_sections)
        
        # 페이지 anchor 구축 (보수적)
        anchors, anchor_stats = _build_page_anchors(paragraphs, score_threshold=0.6)
        
        # 상세 로그
        logger.info(
            "HWPX 페이지 anchor 분석: raw_candidates=%d, excluded=%d, initial=%d, final=%d, plausible_max=%d",
            anchor_stats.get("raw_candidates", 0),
            anchor_stats.get("excluded_candidates", 0),
            anchor_stats.get("initial_anchors", 0),
            anchor_stats.get("final_anchors", 0),
            anchor_stats.get("plausible_max_page", 0)
        )
        
        # 페이지 할당
        page_assignments = _assign_estimated_pages(paragraphs, anchors)
        
        # 섹션별로 텍스트 그룹화 (section fallback용)
        section_texts: Dict[int, List[str]] = {}
        # 페이지별로 텍스트 그룹화 (page_estimated용)
        page_texts: Dict[int, List[str]] = {}
        
        for para_idx, page_no, locator_type, confidence, source in page_assignments:
            para = next((p for p in paragraphs if p.para_idx == para_idx), None)
            if para:
                if locator_type == "section":
                    # section fallback: section_idx 기반
                    if page_no not in section_texts:
                        section_texts[page_no] = []
                    section_texts[page_no].append(para.text)
                else:
                    # page_estimated: page_no 기반
                    if page_no not in page_texts:
                        page_texts[page_no] = []
                    page_texts[page_no].append(para.text)
        
        # 통계 로그
        page_estimated_count = sum(1 for _, _, lt, _, _ in page_assignments if lt == "page_estimated")
        section_fallback_count = sum(1 for _, _, lt, _, _ in page_assignments if lt == "section")
        
        logger.info(
            "HWPX 추출 완료: %s (섹션 %d개, page_estimated: %d문단, section: %d문단)",
            path, total_sections, page_estimated_count, section_fallback_count
        )
        
        # locator_type 결정
        # 주의: OCR 텍스트는 _extract_hwpx_paragraphs 안에서 이미 paragraph 흐름에 inline 삽입됨.
        # 별도 섹션으로 따로 append하지 않음 — 본문+이미지 OCR이 같은 청크 안에 자연스럽게 결합되도록.
        if page_estimated_count > 0:
            # page_estimated가 있으면 page_estimated 사용
            result: List[Tuple[int, str]] = []
            for page_no in sorted(page_texts.keys()):
                combined_text = "\n".join(page_texts[page_no])
                result.append((page_no, combined_text))
            return (result, "page_estimated")
        else:
            # page_estimated가 없으면 section fallback
            result: List[Tuple[int, str]] = []
            for section_idx in sorted(section_texts.keys()):
                combined_text = "\n".join(section_texts[section_idx])
                result.append((section_idx, combined_text))
            return (result, "section")

    except Exception as e:
        # ZIP이 아닌 파일 — 매직바이트 기반 폴백 (HWPML, HTML)
        import zipfile
        if isinstance(e, zipfile.BadZipFile) or "not a zip file" in str(e).lower():
            try:
                with open(path, 'rb') as f:
                    magic_bytes = f.read(16)
            except Exception:
                magic_bytes = b''

            stripped = magic_bytes.lstrip(b'\xef\xbb\xbf')

            # OLE2(HWP) 감지: 확장자는 .hwpx이지만 실제로는 전통 HWP
            if magic_bytes.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                logger.warning("HWPX 파일이 OLE2(HWP) 포맷으로 감지됨, HWP 추출로 폴백: %s", path)
                try:
                    return extract_hwp_pages(
                        path,
                        ocr_client=ocr_client,
                        image_upscale_threshold_px=image_upscale_threshold_px,
                        image_upscale_factor=image_upscale_factor,
                    )
                except Exception as hwp_err:
                    logger.warning("HWP(OLE2) 추출 실패: %s, 에러: %s", path, hwp_err)

            # HWPML(XML) 감지
            if stripped.startswith(b'<?xml') or stripped.upper().startswith(b'<HWPML'):
                logger.warning("HWPX 파일이 HWPML(XML) 포맷으로 감지됨, HWPML 추출로 폴백: %s", path)
                try:
                    paragraphs, total_sections = _extract_hwpml_paragraphs(path)
                    if paragraphs:
                        logger.info("HWPML 문단 추출 완료: %s (총 %d개 문단, %d개 섹션)", path, len(paragraphs), total_sections)
                        result: List[Tuple[int, str]] = []
                        section_texts_fb: Dict[int, List[str]] = {}
                        for para in paragraphs:
                            section_texts_fb.setdefault(para.section_idx, []).append(para.text)
                        for si in sorted(section_texts_fb.keys()):
                            result.append((si, "\n".join(section_texts_fb[si])))
                        return (result, "section")
                except Exception as hwpml_err:
                    logger.warning("HWPML 추출 실패: %s, 에러: %s", path, hwpml_err)

            # HTML 감지
            if stripped.upper().startswith(b'<HTML') or stripped.upper().startswith(b'<!DOC'):
                logger.warning("HWPX 파일이 HTML 포맷으로 감지됨, HTML 추출로 폴백: %s", path)
                try:
                    paragraphs, total_sections = _extract_html_paragraphs(path)
                    if paragraphs:
                        logger.info("HTML 문단 추출 완료: %s (총 %d개 문단)", path, len(paragraphs))
                        result: List[Tuple[int, str]] = []
                        section_texts_fb: Dict[int, List[str]] = {}
                        for para in paragraphs:
                            section_texts_fb.setdefault(para.section_idx, []).append(para.text)
                        for si in sorted(section_texts_fb.keys()):
                            result.append((si, "\n".join(section_texts_fb[si])))
                        return (result, "section")
                except Exception as html_err:
                    logger.warning("HTML 추출 실패: %s, 에러: %s", path, html_err)

            raise ValueError(
                f"HWPX 파일이 ZIP/OLE2/HWPML/HTML 어느 포맷에도 해당하지 않습니다 (매직바이트: {magic_bytes[:16].hex()}). "
                f"파일이 손상되었거나 지원하지 않는 포맷일 수 있습니다: {path}"
            ) from e

        logger.error(f"HWPX 추출 실패: {path}, 에러: {e}")
        raise


def extract_hwpx_text(path: str) -> str:
    """HWPX → 전체 텍스트 (하위 호환성)"""
    if gethwp is None:
        raise ImportError(
            "gethwp 모듈이 설치되지 않았습니다. HWPX 파일 처리를 위해 다음 명령어로 설치하세요:\n"
            "pip install gethwp"
        )
    
    try:
        text = gethwp.read_hwpx(path)
        text = _strip_null_chars(text)
        return text or ""
    except Exception as e:
        logger.error(f"HWPX 추출 실패: {path}, 에러: {e}")
        raise


def extract_text_txt(path: str) -> str:
    """TXT → 전체 텍스트"""
    for enc in ("utf-8", "cp949"):
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            text = _clean_common_noise(_normalize_unicode(_strip_null_chars(text)))
            return text
        except UnicodeDecodeError:
            continue

    raise RuntimeError(f"TXT 파일 인코딩을 알 수 없습니다: {path}")


def extract_doc_pages_via_pdf(path: str, ocr_client=None, **ocr_kwargs) -> List[Tuple[int, str]]:
    """DOC → PDF 변환 후 페이지별 추출 (LibreOffice 사용)

    LibreOffice를 사용하여 DOC를 PDF로 변환한 후 PyMuPDF로 페이지별 추출.
    ocr_client가 주어지면 변환된 PDF에 OCR도 함께 적용.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.splitext(os.path.basename(path))[0]
            pdf_path = os.path.join(tmpdir, base + ".pdf")

            timeout = _calculate_timeout(path)
            file_size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info("DOC → PDF 변환 시작: %s (%.1fMB, 타임아웃: %d초)", path, file_size_mb, timeout)

            pdf_cmd = [
                "soffice",
                "--headless",
                "--invisible",
                "--nocrashreport",
                "--nodefault",
                "--nofirststartwizard",
                "--nolockcheck",
                "--nologo",
                "--norestore",
                "--convert-to", "pdf",
                "--outdir", tmpdir,
                path,
            ]

            pdf_result = subprocess.run(pdf_cmd, capture_output=True, timeout=timeout)

            if pdf_result.returncode != 0 or not os.path.exists(pdf_path):
                logger.error(
                    "DOC → PDF 변환 실패(returncode=%s, stderr=%s)",
                    pdf_result.returncode,
                    pdf_result.stderr.decode("utf-8", errors="ignore"),
                )
                raise RuntimeError("DOC → PDF 변환에 실패했습니다.")

            if ocr_client is not None:
                pages = extract_pdf_pages_with_ocr(pdf_path, ocr_client=ocr_client, **ocr_kwargs)
            else:
                pages = extract_pdf_pages(pdf_path)

            logger.info("DOC → PDF 변환 성공: %s (페이지 %d개, ocr=%s)", path, len(pages), ocr_client is not None)
            return pages

    except Exception as e:
        logger.error(f"DOC → PDF 변환 실패: {path}, 에러: {e}")
        raise


def extract_doc_pages(path: str, use_libreoffice: bool = True, ocr_client=None, **ocr_kwargs) -> List[Tuple[int, str]]:
    """DOC → (page_no, text) 리스트 (구버전 Word 형식)

    Args:
        path: DOC 파일 경로
        use_libreoffice: True이면 LibreOffice로 PDF 변환 후 추출 (페이지 정보 포함)
                        False이면 textract/win32com으로 직접 추출 (페이지 정보 없음)
        ocr_client: OCR 클라이언트 (LibreOffice 경로에서만 동작).
    """
    if use_libreoffice:
        try:
            return extract_doc_pages_via_pdf(path, ocr_client=ocr_client, **ocr_kwargs)
        except Exception as e:
            logger.warning(f"LibreOffice 변환 실패, textract/win32com으로 fallback (OCR 미지원): {e}")
    
    # textract/win32com으로 직접 추출 (fallback)
    try:
        # 방법 1: textract 라이브러리 시도
        try:
            import textract
            text = textract.process(path).decode('utf-8')
            if text:
                logger.info("textract으로 DOC 추출 성공 (페이지 정보 없음)")
                return [(1, text)]
        except ImportError:
            logger.debug("textract 라이브러리가 설치되지 않았습니다.")
        except Exception as e:
            logger.debug(f"textract로 DOC 추출 실패: {e}")
        
        # 방법 2: Windows 환경에서 win32com 시도
        if os.name == 'nt':  # Windows
            try:
                import win32com.client
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                doc = word.Documents.Open(os.path.abspath(path))
                text = doc.Content.Text
                doc.Close()
                word.Quit()
                if text:
                    logger.info("win32com으로 DOC 추출 성공 (페이지 정보 없음)")
                    return [(1, text)]
            except Exception as e:
                logger.debug(f"win32com으로 DOC 추출 실패: {e}")
        
        # 모든 방법 실패
        raise RuntimeError(
            "DOC 파일 추출에 실패했습니다. LibreOffice를 사용하거나 다음 중 하나를 설치하세요:\n"
            "1. textract: pip install textract\n"
            "2. Windows: pywin32 설치 및 Microsoft Word 설치"
        )
    
    except Exception as e:
        logger.error(f"DOC 추출 실패: {path}, 에러: {e}")
        raise


def extract_ppt_text(path: str) -> str:
    """PPT → 전체 텍스트 (레거시)"""
    pages = extract_ppt_pages(path)
    return "\n".join(text for _, text in pages)


def extract_ppt_pages(path: str, ocr_client=None, **ocr_kwargs) -> List[Tuple[int, str]]:
    """PPT → (slide_no, text) 리스트 (구버전 PowerPoint 형식).

    LibreOffice로 PDF 변환 후 슬라이드별 텍스트 추출.
    ocr_client가 주어지면 변환된 PDF에 OCR도 함께 적용.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.splitext(os.path.basename(path))[0]
            pdf_path = os.path.join(tmpdir, base + ".pdf")

            logger.info("PPT → PDF 변환 시작: %s", path)
            pdf_cmd = [
                "soffice",
                "--headless",
                "--invisible",
                "--nocrashreport",
                "--nodefault",
                "--nofirststartwizard",
                "--nolockcheck",
                "--nologo",
                "--norestore",
                "--convert-to", "pdf",
                "--outdir", tmpdir,
                path,
            ]
            pdf_result = subprocess.run(pdf_cmd, capture_output=True, timeout=60)
            if pdf_result.returncode != 0 or not os.path.exists(pdf_path):
                logger.error(
                    "PPT → PDF 변환 실패(returncode=%s, stderr=%s)",
                    pdf_result.returncode,
                    pdf_result.stderr.decode("utf-8", errors="ignore"),
                )
                raise RuntimeError("PPT → PDF 변환에 실패했습니다.")

            if ocr_client is not None:
                pages = extract_pdf_pages_with_ocr(pdf_path, ocr_client=ocr_client, **ocr_kwargs)
            else:
                pages: List[Tuple[int, str]] = []
                with fitz.open(pdf_path) as doc:
                    for slide_no, page in enumerate(doc, start=1):
                        txt = page.get_text("text")
                        if txt:
                            txt = _remove_pdf_hyphens(txt)
                            txt = _normalize_unicode(txt)
                            txt = _strip_null_chars(txt)
                            txt = _clean_common_noise(txt)
                            pages.append((slide_no, txt))

            logger.info("PPT → PDF 변환 성공: %s (슬라이드 %d개, ocr=%s)", pdf_path, len(pages), ocr_client is not None)
            return pages

    except Exception as e:
        logger.error(f"PPT 추출 실패: {path}, 에러: {e}")
        raise

