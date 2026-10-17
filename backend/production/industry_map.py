"""수주서 "사업구분" 원문 → 7개 산업 분야 대응표 (specs/05-production.md 1절)

기업 확인 전 임시 기준: 사업구분 원문에 아래 낱말이 들어 있으면 그 분야로 본다 (위에서부터 먼저 맞는 것).
대응표에 없는 값은 "기타". 사업구분 전체 목록을 받으면 이 표를 고친다.
"""

INDUSTRIES = ["상하수도", "발전소", "가스", "오일", "석유", "민간 플랜트", "기타"]

KEYWORD_RULES = [
    ("상하수도", "상하수도"),  # 예: 상하수도(지자체)
    ("발전", "발전소"),
    ("가스", "가스"),
    ("오일", "오일"),
    ("석유", "석유"),
    ("플랜트", "민간 플랜트"),
]


def to_industry(business_type_raw):
    text = (business_type_raw or "").strip()
    for keyword, industry in KEYWORD_RULES:
        if keyword in text:
            return industry
    return "기타"
