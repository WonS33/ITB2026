"""PDF 양식(수주서·출장보고서) 읽기 도구

샘플 PDF에서 확인한 내용 (specs/05-production.md 4절)
1) 글꼴이 숫자·일부 기호를 특수 코드로 저장한다 → 아래 CHAR_MAP으로 되돌린다
     U+E071~U+E07A → 0~9,  U+E093 → ,  U+E094 → .  U+E095 → :
2) 항목 이름 바로 아래에 값이 있다 (2~3단 배치)
     → "항목 이름 아래부터 다음 항목 이름(또는 구역 제목) 전까지, 같은 칸 안의 글자"를 값으로 읽는다
3) 긴 값은 "…"로 잘려 있다 → 확인 화면에서 사람이 고친다
"""

import logging
from dataclasses import dataclass

import pdfplumber

CHAR_MAP = {0xE071 + i: str(i) for i in range(10)}
CHAR_MAP.update({0xE093: ",", 0xE094: ".", 0xE095: ":"})

TRUNCATED = "…"


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


def read_pages(file):
    """PDF의 페이지마다 (글자 목록, 페이지 너비, 페이지 높이)를 돌려준다"""
    logging.getLogger("pdfminer").setLevel(logging.ERROR)  # 글꼴 경고 숨김
    pages = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            words = [
                Word(w["text"].translate(CHAR_MAP).strip(), w["x0"], w["x1"], w["top"], w["bottom"])
                for w in page.extract_words(keep_blank_chars=True, x_tolerance=2)
            ]
            pages.append(FormPage([w for w in words if w.text], page.width, page.height))
    return pages


class FormPage:
    def __init__(self, words, width, height):
        self.words = words
        self.width = width
        self.height = height

    def find(self, text):
        return next((w for w in self.words if w.text == text), None)

    def _same_line(self, a, b):
        return abs(a.top - b.top) < 1.5

    def _right_bound(self, label):
        """같은 줄에서 오른쪽에 있는 다음 항목 이름의 x 위치 = 이 칸의 오른쪽 끝"""
        lefts = [w.x0 for w in self.words if self._same_line(w, label) and w.x0 > label.x1]
        return min(lefts, default=self.width)

    def _lines(self, words):
        """글자들을 줄 단위로 묶어 왼쪽부터 이어 붙인다"""
        lines = []
        for w in sorted(words, key=lambda w: (round(w.top), w.x0)):
            if lines and abs(lines[-1][0] - w.top) < 1.5:
                lines[-1][1].append(w.text)
            else:
                lines.append((w.top, [w.text]))
        return [" ".join(parts) for _top, parts in lines]

    def value(self, label_text, labels, headings):
        """항목 이름 아래 값. labels: 이 양식의 모든 항목 이름, headings: 구역 제목(가로 전체를 나눔)"""
        label = self.find(label_text)
        if label is None:
            return None
        left, right = label.x0 - 3, self._right_bound(label)
        in_column = lambda w: left <= w.x0 < right
        # 아래쪽 끝: 같은 칸의 다음 항목 이름, 또는 (칸과 관계없이) 다음 구역 제목
        stops = [w.top for w in self.words if w.top > label.top + 1 and (
            (w.text in labels and in_column(w)) or w.text in headings)]
        bottom = min(stops, default=self.height + 1)
        words = [w for w in self.words if label.top + 1 < w.top < bottom and in_column(w) and w.text not in labels]
        return "\n".join(self._lines(words))

    def table(self, header_texts, stop_texts):
        """표 읽기: 머리글 칸의 x 위치로 열을 나누고, 머리글 아래부터 stop 글자 전까지를 행으로 읽는다"""
        header = [self.find(t) for t in header_texts]
        if any(h is None for h in header):
            return []
        top = header[0].top
        stops = [w.top for w in self.words if w.top > top + 1 and any(w.text.startswith(s) for s in stop_texts)]
        bottom = min(stops, default=self.height + 1)
        bounds = [h.x0 - 3 for h in header] + [self.width]

        body = [w for w in self.words if top + 1 < w.top < bottom]
        rows = []
        for line_top in sorted({round(w.top, 0) for w in body}):
            line = [w for w in body if abs(round(w.top, 0) - line_top) < 1.5]
            row = {}
            for i, name in enumerate(header_texts):
                cell = [w.text for w in sorted(line, key=lambda w: w.x0) if bounds[i] <= w.x0 < bounds[i + 1]]
                row[name] = " ".join(cell)
            if any(row.values()) and not any(r == row for r in rows):
                rows.append(row)
        return rows
