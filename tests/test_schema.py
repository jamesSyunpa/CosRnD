import unittest
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verify_schema import verify_schema_integrity

class TestSchemaIntegrity(unittest.TestCase):
    def test_schema_matches_models(self):
        """
        데이터베이스 스키마가 SQLAlchemy 모델 정의와 일치하는지 테스트합니다.
        불일치 시 실패합니다.
        """
        result = verify_schema_integrity()
        self.assertTrue(result, "데이터베이스 스키마가 모델과 일치하지 않습니다. 누락된 컬럼을 확인하세요.")

if __name__ == "__main__":
    unittest.main()
