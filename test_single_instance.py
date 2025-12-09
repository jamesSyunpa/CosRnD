# test_single_instance.py
# 단일 인스턴스 기능 테스트용 스크립트

import sys
import os

# main.py의 check_single_instance 함수 임포트
sys.path.insert(0, os.path.dirname(__file__))

# check_single_instance 함수만 테스트
from main import check_single_instance

print("=" * 60)
print("단일 인스턴스 기능 테스트")
print("=" * 60)

if check_single_instance():
    print("\n✓ 프로그램 실행 허용됨")
    print("이 창을 닫지 말고, 다른 터미널에서 다시 이 스크립트를 실행해보세요.")
    print("\n종료하려면 Enter 키를 누르세요...")
    input()
else:
    print("\n✗ 프로그램이 이미 실행 중입니다 (중복 실행 차단됨)")
    sys.exit(0)

print("\n프로그램 종료")
