# -*- coding: utf-8 -*-
"""
자회사(자사) 정보 공통 관리 모듈
- 시스템 설정에서 입력한 회사 정보(국문/영문 회사명, 주소, 연락처, 담당부서 등)를 영구 보존하고,
  품질관리(MSDS, 제품표준서, COA 등) 및 연구문서(견적서, BMR 등) 모든 엑셀/문서에 자동으로 연동합니다.
"""
import os
import json

_DEFAULT_PROFILE = {
    "company_name_ko": "(주)한국피부과학연구소",
    "company_name_en": "Korea Dermatology Research Institute Co., Ltd.",
    "representative": "대표이사",
    "biz_no": "123-45-67890",
    "address_ko": "서울특별시 금천구 디지털로 121 (에이스가산타워)",
    "address_en": "Ace Gasan Tower, 121 Digital-ro, Geumcheon-gu, Seoul, Korea",
    "phone": "02-123-4567",
    "emergency_phone": "02-123-4567",
    "fax": "02-123-4568",
    "email": "rnd@cosmetics.co.kr",
    "website": "www.cosmetics.co.kr",
    "lab_name_ko": "(주)한국피부과학연구소 R&D센터",
    "lab_name_en": "KDRI R&D Center",
    "department_ko": "품질보증팀 / MSDS 담당부서",
    "department_en": "Quality Assurance Team",
    "manager_name": "품질책임자",
    "manager_name_en": "QA Manager / Specialist",
    "form_doc_no": "양0100-01",
    "form_rev_no": "Rev.0"
}

def _get_config_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_dir = os.path.join(base_dir, "config")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "company_profile.json")

def get_company_profile():
    """저장된 자회사 정보를 불러옵니다. 파일이 없으면 기본값을 생성하고 반환합니다."""
    path = _get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                res = dict(_DEFAULT_PROFILE)
                res.update(data)
                return res
        except Exception as e:
            print(f"[경고] 회사 정보 로드 실패: {e}")
    
    # 기본값 파일 저장 후 반환
    save_company_profile(_DEFAULT_PROFILE)
    return dict(_DEFAULT_PROFILE)

def save_company_profile(profile_dict):
    """자회사 정보를 config/company_profile.json 에 영구 저장합니다."""
    path = _get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[오류] 회사 정보 저장 실패: {e}")
        return False
