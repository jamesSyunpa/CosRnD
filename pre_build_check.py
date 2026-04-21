#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Pre-Flight Check Script
빌드 전 필수 검사 항목을 자동으로 확인합니다.
"""

import os
import sys
import subprocess
import configparser
from pathlib import Path

class BuildChecker:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.issues = []
        self.warnings = []
        self.info = []
        
    def check_all(self):
        """모든 검사 항목 실행"""
        print("=" * 70)
        print(" 프로그램 빌드 전 검사 시작")
        print("=" * 70)
        
        self.check_spec_file()
        self.check_main_py()
        self.check_dependencies()
        self.check_config_files()
        self.check_resources()
        
        self.print_results()
        
    def check_spec_file(self):
        """Spec 파일 검사"""
        print("\n[1] Spec 파일 검사...")
        spec_file = self.project_root / '화장품연구관리_v59.spec'
        
        if not spec_file.exists():
            self.issues.append("❌ Spec 파일 없음: 화장품연구관리_v59.spec")
            return
        
        with open(spec_file, 'r', encoding='utf-8') as f:
            spec_content = f.read()
        
        # 필수 항목 확인
        checks = {
            'pathex=[project_root]': 'pathex에 절대 경로 추가',
            'hiddenimports=': 'hiddenimports 설정',
            'database.db_manager': 'database.db_manager 모듈 포함',
            'customtkinter': 'customtkinter 포함',
            'sqlalchemy': 'sqlalchemy 포함',
        }
        
        for check, description in checks.items():
            if check in spec_content:
                self.info.append(f"✅ {description}: 확인됨")
            else:
                self.warnings.append(f"⚠️  {description}: 미확인")
    
    def check_main_py(self):
        """main.py 검사"""
        print("\n[2] main.py 검사...")
        main_file = self.project_root / 'main.py'
        
        if not main_file.exists():
            self.issues.append("❌ main.py 파일 없음")
            return
        
        with open(main_file, 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        # run_tasks 함수 개선 확인
        if 'task_failed = False' in main_content:
            self.info.append("✅ run_tasks() 무한루프 방지 로직: 추가됨")
        else:
            self.warnings.append("⚠️  run_tasks() 개선이 필요할 수 있음")
        
        # on_closing 강제 종료 로직 확인
        if 'TerminateProcess' not in main_content:
            self.info.append("✅ on_closing() 과도한 강제 종료 로직: 제거됨")
        else:
            self.issues.append("❌ on_closing()에 여전히 TerminateProcess 호출 있음")
        
        # 단순한 sys.exit 확인
        if 'sys.exit(0)' in main_content and 'threading.Timer' not in main_content.split('def on_closing')[1].split('def ')[0]:
            self.info.append("✅ on_closing() 종료 로직: 단순화됨")
    
    def check_dependencies(self):
        """의존성 검사"""
        print("\n[3] 의존성 검사...")
        
        required_packages = [
            'customtkinter',
            'sqlalchemy',
            'bcrypt',
            'openpyxl',
            'pandas',
            'pillow',
            'tkcalendar',
        ]
        
        missing = []
        for pkg in required_packages:
            try:
                __import__(pkg)
                self.info.append(f"✅ {pkg}: 설치됨")
            except ImportError:
                missing.append(pkg)
        
        if missing:
            self.issues.append(f"❌ 누락된 패키지: {', '.join(missing)}")
    
    def check_config_files(self):
        """설정 파일 검사"""
        print("\n[4] 설정 파일 검사...")
        
        config_file = self.project_root / 'config.ini'
        if config_file.exists():
            self.info.append(f"✅ config.ini: 존재함")
        else:
            self.warnings.append(f"⚠️  config.ini: 없음 (초기 실행 시 생성됨)")
        
        version_file = self.project_root / 'VERSION'
        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                version = f.read().strip()
            self.info.append(f"✅ VERSION: {version}")
        else:
            self.warnings.append(f"⚠️  VERSION 파일: 없음")
    
    def check_resources(self):
        """리소스 파일 검사"""
        print("\n[5] 리소스 파일 검사...")
        
        resources = {
            'Icon.ico': '아이콘',
            'assets': '자산 폴더',
            'database': '데이터베이스 폴더',
            'modules': '모듈 폴더',
            'utils': '유틸리티 폴더',
        }
        
        for resource, description in resources.items():
            path = self.project_root / resource
            if path.exists():
                self.info.append(f"✅ {description} ({resource}): 존재함")
            else:
                self.warnings.append(f"⚠️  {description} ({resource}): 없음")
    
    def print_results(self):
        """결과 출력"""
        print("\n" + "=" * 70)
        print(" 검사 결과")
        print("=" * 70)
        
        if self.issues:
            print("\n🔴 치명적 문제:")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print("\n🟠 경고:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.info:
            print("\n✅ 정상:")
            for item in self.info:
                print(f"  {item}")
        
        print("\n" + "=" * 70)
        if not self.issues:
            print("✅ 빌드 검사 완료 - 빌드 진행 가능합니다!")
        else:
            print(f"❌ 빌드 검사 실패 - {len(self.issues)}개 문제를 해결해주세요.")
        print("=" * 70)
        
        return len(self.issues) == 0

def main():
    # 프로젝트 루트 경로
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
    
    checker = BuildChecker(project_root)
    success = checker.check_all()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
