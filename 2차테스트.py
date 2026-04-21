def suggest_thickener(form_type):
    """
    제형 타입에 따라 권장 점증제 및 사용량을 추천하는 함수
    중화가 필요한 경우 중화제 종류와 권장량도 포함
    """
    suggestions = {
        "클렌징오일": [],
        "W/O 크림": [
            {"name": "세틸알코올", "range": "1.0~3.0%", "note": "감각 개선 및 보조 점증"},
            {"name": "비즈왁스", "range": "0.5~5.0%", "note": "고점도형 연고에 사용"}
        ],
        "연고": [
            {"name": "카보머", "range": "0.2~0.5%", "note": "pH 중화 필요: 트리에탄올아민(TEA) 또는 NaOH, 권장 중화제량: 카보머 대비 약 0.2~0.5배"},
            {"name": "비즈왁스", "range": "1.0~5.0%", "note": "제형 고형화"}
        ],
        "선크림": [
            {"name": "PEG-100 스테아레이트", "range": "1.0~3.0%", "note": "유화안정 + 점증 보조"},
            {"name": "카보머", "range": "0.2~0.5%", "note": "pH 중화 필요: TEA/NaOH 사용, 0.2~0.4%"}
        ],
        "로션": [
            {"name": "하이드록시에틸셀룰로오스", "range": "0.3~1.0%", "note": "점도 및 유동감 부여 (중화 불필요)"},
            {"name": "카보머", "range": "0.2~0.4%", "note": "선명한 젤감 부여, pH 중화 필요: TEA 또는 NaOH, 사용량은 카보머 대비 0.3~0.5배"}
        ],
        "O/W 크림": [
            {"name": "카보머", "range": "0.2~0.5%", "note": "pH 중화 필요: TEA/NaOH 사용, 중화제 비율 0.2~0.4%"},
            {"name": "세테아릴알코올", "range": "1.0~3.0%", "note": "점도 + 안정성"}
        ],
        "세럼": [
            {"name": "잔탄검", "range": "0.1~0.3%", "note": "가벼운 젤감 부여 (중화 불필요)"}
        ],
        "클렌징밀크": [
            {"name": "카보머", "range": "0.2~0.4%", "note": "점도 조절 및 유화 안정, pH 중화 필요: TEA/NaOH 약 0.2~0.5%"}
        ],
        "세정제": [
            {"name": "하이드록시프로필메틸셀룰로오스", "range": "0.3~0.8%", "note": "점도 유지 및 흐름성 부여"}
        ],
        "에센스": [
            {"name": "잔탄검", "range": "0.1~0.3%", "note": "수분감 있는 점도 부여 (중화 불필요)"}
        ],
        "토너": [
            {"name": "하이드록시에틸셀룰로오스", "range": "0.1~0.3%", "note": "약한 점도 + 사용감 개선"}
        ]
    }

    return suggestions.get(form_type, [])

def suggest_moisturizer_interaction(moisturizer_name, thickener_name):
    """
    보습제와 점증제의 상호작용 추천 시스템
    """
    pairs = {
        ("글리세린", "카보머"): "글리세린은 카보머와 함께 사용 시 점도 안정성에 기여하며 투명한 젤 제형을 만들 수 있습니다.",
        ("글리세린", "하이드록시에틸셀룰로오스"): "글리세린은 HEC와 좋은 상용성을 보여 사용감이 부드러워집니다.",
        ("부틸렌글라이콜", "잔탄검"): "부틸렌글라이콜은 잔탄검의 흐름성을 개선하고 점도를 부드럽게 만듭니다.",
        ("프로판디올", "카보머"): "프로판디올은 카보머와의 혼합 시 점도의 균일성과 보습력을 향상시킵니다.",
        ("글리세린", "잔탄검"): "글리세린과 잔탄검 조합은 수분막 형성과 점도의 안정성이 뛰어납니다."
    }
    key = (moisturizer_name, thickener_name)
    reverse_key = (thickener_name, moisturizer_name)
    return pairs.get(key) or pairs.get(reverse_key) or "이 조합에 대한 특이 상호작용 정보는 없습니다."

# 예시 사용법
if __name__ == "__main__":
    form_type = "로션"
    thickeners = suggest_thickener(form_type)
    print(f"[제형: {form_type}] 추천 점증제 목록")
    for thick in thickeners:
        print(f"- {thick['name']}: 사용량 {thick['range']} ({thick['note']})")

    print("\n상호작용 예시:")
    print(suggest_moisturizer_interaction("글리세린", "카보머"))
    print(suggest_moisturizer_interaction("부틸렌글라이콜", "잔탄검"))
