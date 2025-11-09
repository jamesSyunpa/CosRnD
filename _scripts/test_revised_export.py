import sys, os, tempfile
sys.path.append(r"c:\\Users\\neon5\\Desktop\\RnD_플랫폼")

from modules.excel_handler import export_production_formulation_to_excel

production_data = {
    "details": {
        "제품명": "테스트 제품",
        "LAB NO.": "LAB-001",
        "거래처": "고객A",
        "적용일": "2025-11-02",
        "승인자": "홍길동",
        "생산코드": "PRD-123",
        "차수": "1",
        "생산량(kg)": "100",
        "상태": "승인",
        "출력일시": "2025-11-02 10:00",
    },
    "items": [
        {
            "Ph": "A",
            "구분": "베이스",
            "코드": "MAT-001",
            "원료명": "정제수",
            "함량(%)": "70.0000",
            "생산량(kg)": "70",
            "제조공정": "1) 투입\n2) 교반",
            "공정검사": "pH 측정"
        },
        {
            "Ph": "",
            "구분": "첨가",
            "코드": "MAT-002",
            "원료명": "글리세린",
            "함량(%)": "5.5000",
            "생산량(kg)": "5.5",
            "제조공정": "투입",
            "공정검사": "외관"
        },
        {
            "Ph": "B",
            "구분": "첨가",
            "코드": "MAT-003",
            "원료명": "향료",
            "함량(%)": "0.1000",
            "생산량(kg)": "0.1",
            "제조공정": "마지막에 첨가",
            "공정검사": "향 확인"
        },
    ],
}

fd, tmp_path = tempfile.mkstemp(suffix=".xlsx"); os.close(fd)
print("Export path:", tmp_path, flush=True)
export_production_formulation_to_excel(
    production_data,
    default_filename="production_revised.xlsx",
    file_path=tmp_path,
    open_print_preview=True,
    mode="revised",
)
print("Done export & preview trigger.", flush=True)
