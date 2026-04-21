# 빌드 및 무한루프 문제 상세 분석 보고서
**작성 일자**: 2026년 2월 11일  
**버전**: v59  
**심각도**: 🔴 CRITICAL (프로그램 강제 종료 및 시스템 손상 발생)

---

## 1. 발견된 주요 문제점

### 1.1 **show_pre_login_splash()의 재귀 호출 문제** 🔴 CRITICAL
**위치**: [main.py](main.py#L836)  
**문제**: 로그인 前 스플래시 화면 초기화 중 무한루프 가능성

```python
def run_tasks(task_index=0):
    if task_index < total_tasks:
        # ... task 실행 ...
        self.after(50, lambda: run_tasks(task_index + 1))  # ⚠️ 재귀 호출
    else:
        # ... 완료 처리 ...
        self.after(300, lambda: (splash.destroy(), on_load_complete()))
```

**근본 원인**:
- `self.after()` 내에서 동일 함수 `run_tasks()`를 재귀 호출
- 예외 처리 없이 대기 후 다음 작업 호출
- 만약 `task_func()`에서 예외 발생 → `messagebox.showerror()` 표시 후 `return` → 다음 작업 미호출 → 스플래시가 영구적으로 멈춤
- 사용자가 무한 대기 상태에 빠질 가능성

**관련 작업**:
1. [main.py#L990-1020](main.py#L990-L1020) - 3가지 초기화 작업 (설정 로드, 패치 적용, DB 초기화)

---

### 1.2 **on_closing() 함수의 과도한 종료 로직** 🔴 CRITICAL  
**위치**: [main.py#L2100](main.py#L2100)

**문제 코드**:
```python
def on_closing(self):
    # ... 정상 종료 로직 ...
    finally:
        # ⚠️ 과도한 강제 종료 메커니즘
        try:
            if os.name == 'nt':
                import threading, ctypes
                def _force_kill():
                    ctypes.windll.kernel32.TerminateProcess(
                        ctypes.windll.kernel32.GetCurrentProcess(), 0
                    )
                t = threading.Timer(0.5, _force_kill)  # 0.5초 후 강제 종료
                t.daemon = True
                t.start()
        
        # 여러 종료 시도
        import threading
        t2 = threading.Timer(0.2, lambda: os._exit(0))
        t2.daemon = True
        t2.start()
        
        sys.exit(0)  # 또는
        os._exit(0)   # 또는 TerminateProcess()
```

**위험 요소**:
- **다중 종료 메커니즘**: `sys.exit()`, `os._exit()`, `TerminateProcess()` 동시 호출
- **스레드 타이머로 인한 강제 종료**: 종료 중 정리 작업 미완료 가능성
- **데이터 손상 위험**: DB 연결 완전 정리 전 강제 종료 시 DB 파일 손상 가능
- **메모리/파일 잠금**: 프로세스 강제 종료 시 리소스 누수

---

### 1.3 **데이터베이스 초기화 작업의 오류 처리 부재** 🟠 HIGH  
**위치**: [main.py#L951-1050](main.py#L951-L1050)  
**위치**: [database/db_manager.py#L210-430](database/db_manager.py#L210-L430)

**문제**:
```python
def init_database():
    try:
        if self.handle_restart_db_sync():
            print("=== 재시작 DB 동기화 완료 ===")
        
        db_manager.setup_database(...)
        return True
    except Exception as e:
        print(f"데이터베이스 초기화 실패: {e}")
        return False
```

**위험 요소**:
- `return False` 이후 `run_tasks()`의 exception handler가 없음
- 실패 시 스플래시가 영구적으로 멈춤
- 재시도 로직이 없음

---

### 1.4 **PyInstaller Spec 파일 설정 부족** 🟠 HIGH  
**위치**: [화장품연구관리_v59.spec](화장품연구관리_v59.spec)

**현재 설정 분석**:
```python
a = Analysis(
    ['C:\\Users\\neon5\\Desktop\\R&D_Flatform_버전관리\\CosRnD_v59\\main.py'],
    pathex=[],
    binaries=[],  # ⚠️ 필수 바이너리 누락 가능
    datas=[
        ('assets\\*', 'assets'), 
        ('data\\*', 'data'), 
        ('database\\*', 'database'), 
        ('modules\\*', 'modules'), 
        ('utils\\*', 'utils'), 
        ('config.ini', '.'), 
        ('VERSION', '.'), 
        ('Icon.ico', '.'), 
        ('icon.ico', '.')
    ],
    hiddenimports=[],  # ⚠️ 동적 import된 모듈 누락 가능
    hookspath=['hooks'],  # hooks 폴더 경로 설정 필요
    runtime_hooks=[
        'hooks/pyi_rth_sqlite.py',  # SQLite hook 설정
        'hooks/pyi_rth_tkinter.py'  # Tkinter hook 설정
    ],
```

**발견된 문제**:
1. **동적 임포트 모듈 누락**
   - `from database import db_manager` (동적)
   - `from modules import *` (동적)
   - `from utils import *` (동적)

2. **필수 바이너리 누락**
   - SQLite3 관련 DLL (`sqlite3.dll`, `_sqlite3.pyd`)
   - TCL/TK 라이브러리

3. **Hook 설정 불완전**
   - `hookspath=['hooks']`만 설정 → 절대 경로 필요
   - SQLite hook이 제대로 적용되지 않았을 가능성

---

### 1.5 **check_single_instance() 함수의 뮤텍스 문제** 🟠 MEDIUM  
**위치**: [main.py#L163-240](main.py#L163-L240)

**문제**:
```python
def check_single_instance():
    # Windows: Named Mutex 생성
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    
    # ⚠️ 뮤텍스 핸들이 전역 변수로 저장되지만:
    globals()['_app_mutex_handle'] = mutex
```

**위험 요소**:
- 뮤텍스 핸들이 제대로 관리되지 않으면 OS 리소스 누수
- 프로그램 강제 종료 시 뮤텍스가 해제되지 않음

---

## 2. 각 컴포넌트별 상세 분석

### 2.1 빌드 구성 (Spec 파일)

| 구성 요소 | 현재 상태 | 권장 수정 | 우선순위 |
|---------|---------|---------|---------|
| `pathex` | 비어있음 | 프로젝트 루트 경로 추가 | 🔴 |
| `binaries` | 비어있음 | SQLite/TCL DLL 명시 추가 | 🔴 |
| `hiddenimports` | 비어있음 | 동적 import 모듈 추가 | 🔴 |
| `hookspath` | 상대 경로 | 절대 경로로 수정 | 🟠 |
| `runtime_hooks` | SQLite/TK | 확인 및 강화 | 🟠 |
| `console` | False | ✅ (올바름) | ✅ |

### 2.2 초기화 순서 분석

```
main.py (시작)
  ├─ check_single_instance()  ✅
  ├─ App.__init__()           ✅
  │   └─ show_pre_login_splash()  ⚠️ 무한루프 위험
  │       └─ run_tasks() 재귀 호출
  │           ├─ load_app_settings()  ✅
  │           ├─ run_auto_patches()   ✅
  │           └─ init_database()      ⚠️ 재시도 로직 없음
  │
  └─ app.mainloop()          ⚠️ 강제 종료 로직과 충돌
```

---

## 3. 무한루프 시나리오 분석

### 시나리오 1: 스플래시 화면 영구 로딩
```
1. show_pre_login_splash() 호출
2. run_tasks(0) 호출 (설정 로드)
3. load_app_settings() 정상 완료
4. run_tasks(1) 호출 (패치 적용) - after(50ms)
5. run_auto_patches() 정상 완료
6. run_tasks(2) 호출 (DB 초기화) - after(50ms)
7. init_database() 실패 → messagebox.showerror() 표시 → return
8. ⚠️ 다음 run_tasks(3) 호출 안됨 → 스플래시가 영구적으로 멈춤
9. 사용자가 무한 대기 상태에 빠짐
```

### 시나리오 2: 시스템 리소스 고갈 (CPU 사용률 100%)
```
1. mainloop() 실행 중 UI 이벤트 발생
2. 이벤트 핸들러에서 UI 갱신
3. UI 갱신이 다시 같은 이벤트 발생
4. → 무한 이벤트 루프 형성
5. CPU 사용률 100% → 시스템 응답 불가 → 컴퓨터 "박살"
```

### 시나리오 3: 강제 종료 중 데이터베이스 손상
```
1. 정상적으로 프로그램 실행 중
2. 사용자가 프로그램 종료 (X 버튼 클릭)
3. on_closing() 실행 → DB 연결 정리 중...
4. ⚠️ Timer(0.2, os._exit(0)) 동시 실행
5. DB 정리 전에 프로세스 강제 종료
6. 파일 시스템 캐시 미플러시 → SQLite DB 파일 손상
7. 다음 실행 시 DB 복구 불가능 → 데이터 손실
```

---

## 4. 권장 해결 방안

### 4.1 긴급 조치 (즉시 적용)

#### 1️⃣ run_tasks() 함수 개선
```python
def run_tasks(task_index=0):
    if task_index < total_tasks:
        description, task_func = tasks[task_index]
        
        try:
            task_func()
            # ... 프로그래스 업데이트 ...
        except Exception as e:
            print(f"Task failed: {description} - {e}")
            messagebox.showerror("Error", f"Failed: {description}\n{e}")
            # ⚠️ 중요: 정상 완료 상태로 진행
            progress_bar.set(1.0)
            progress_label.configure(text="Failed. Restart required.")
            splash.update_idletasks()
            time.sleep(2)
            splash.destroy()
            self.destroy()
            sys.exit(1)
            return  # 명시적 return
        
        # ... (현재 로직) ...
        self.after(50, lambda: run_tasks(task_index + 1))
    else:
        # 완료 처리
        progress_label.configure(text=done_text)
        progress_bar.set(1)
        splash.update_idletasks()
        
        try:
            if not db_manager.Session:
                raise RuntimeError("DB not initialized")
            
            with db_manager.get_session() as session:
                session.execute(text("SELECT 1"))
            
            self.after(300, lambda: (splash.destroy(), on_load_complete()))
        except Exception as e:
            print(f"Final check failed: {e}")
            messagebox.showerror("DB Error", f"{e}")
            splash.destroy()
            self.destroy()
            sys.exit(1)
```

#### 2️⃣ on_closing() 함수 단순화
```python
def on_closing(self):
    """프로그램 종료 처리"""
    try:
        print(f"{datetime.now()}: 프로그램 종료 중...")
        
        # 1. 설정 저장
        self.save_app_settings()
        self.save_recent_actions()
        
        # 2. DB 연결 정리 (타임아웃 포함)
        try:
            db_manager.dispose_engine()
        except Exception as e:
            print(f"DB cleanup error: {e}")
        
        # 3. UI 정리
        self.quit()
        
    except Exception as e:
        print(f"Closing error: {e}")
    finally:
        # ✅ 단순한 종료 메커니즘만 사용
        sys.exit(0)
```

#### 3️⃣ Spec 파일 수정
```python
# 화장품연구관리_v59.spec
import sys
import os

project_root = r'C:\Users\neon5\Desktop\R&D_Flatform_버전관리\CosRnD_v59'

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],  # ✅ 절대 경로 추가
    binaries=[],  # SQLite는 자동으로 포함됨
    datas=[
        (os.path.join(project_root, 'assets'), 'assets'),
        (os.path.join(project_root, 'data'), 'data'),
        (os.path.join(project_root, 'database'), 'database'),
        (os.path.join(project_root, 'modules'), 'modules'),
        (os.path.join(project_root, 'utils'), 'utils'),
        (os.path.join(project_root, 'config.ini'), '.'),
        (os.path.join(project_root, 'VERSION'), '.'),
        (os.path.join(project_root, 'Icon.ico'), '.'),
    ],
    hiddenimports=[
        'database.db_manager',
        'database.models',
        'modules.login',
        'modules.home_frame',
        'modules.security',
        'customtkinter',
        'PIL',
        'sqlalchemy',
        'bcrypt',
        'openpyxl',
        'pandas',
        'tkcalendar',
    ],
    hookspath=[os.path.join(project_root, 'hooks')],  # ✅ 절대 경로
    hooksconfig={},
    runtime_hooks=[
        os.path.join(project_root, 'hooks/pyi_rth_sqlite.py'),  # ✅ 절대 경로
        os.path.join(project_root, 'hooks/pyi_rth_tkinter.py'),
    ],
    excludes=['matplotlib', 'numpy'],  # 불필요한 라이브러리 제외
    noarchive=False,
    optimize=0,
)

# ... 나머지 설정 동일 ...
```

### 4.2 중기 개선 사항

1. **DB 초기화 재시도 로직 추가**
   ```python
   def init_database_with_retry(max_retries=3):
       for attempt in range(max_retries):
           try:
               db_manager.setup_database(...)
               return True
           except Exception as e:
               if attempt < max_retries - 1:
                   print(f"Retry {attempt + 1}/{max_retries}...")
                   time.sleep(1)  # 1초 대기 후 재시도
               else:
                   raise
   ```

2. **에러 로깅 강화**
   ```python
   def log_error_to_file(error_text):
       import logging
       logging.basicConfig(
           filename='app_errors.log',
           level=logging.ERROR,
           format='%(asctime)s - %(levelname)s - %(message)s'
       )
       logging.error(error_text)
   ```

3. **뮤텍스 정리 추가**
   ```python
   def on_closing(self):
       # ... 기존 코드 ...
       try:
           if '_app_mutex_handle' in globals():
               win32api.CloseHandle(globals()['_app_mutex_handle'])
       except:
           pass
   ```

---

## 5. 테스트 체크리스트

- [ ] **빌드 테스트**
  - [ ] `pyinstaller 화장품연구관리_v59.spec`으로 빌드 성공 확인
  - [ ] exe 크기 확인 (이상 크기 변화 감지)
  - [ ] 빌드 로그에서 경고/오류 확인

- [ ] **실행 테스트**
  - [ ] 프로그램 시작 시 스플래시 화면 최대 10초 이내 로드
  - [ ] 초기화 과정에서 CPU 사용률 >50% 유지 (무한루프 탐지)
  - [ ] 메모리 사용량 500MB 이하 유지

- [ ] **예외 처리 테스트**
  - [ ] DB 초기화 실패 시 사용자 알림
  - [ ] 프로그램 정상 종료
  - [ ] DB 파일 무결성 유지

- [ ] **리소스 정리 테스트**
  - [ ] 프로그램 종료 후 뮤텍스 해제 확인 (중복 실행 가능)
  - [ ] 프로세스 완전 종료 (작업 관리자 확인)
  - [ ] DB 파일 잠금 해제

---

## 6. 추가 권장 사항

### 6.1 건강성 검사 도구 추가
```python
# check_syntax_verbose.py 개선
def check_runtime_health():
    issues = []
    
    # 1. SQLite 가용성
    try:
        import sqlite3
        test_conn = sqlite3.connect(':memory:')
        test_conn.execute('SELECT 1')
        test_conn.close()
    except Exception as e:
        issues.append(f"SQLite unavailable: {e}")
    
    # 2. 필수 모듈 확인
    required_modules = ['customtkinter', 'sqlalchemy', 'bcrypt', 'PIL']
    for mod in required_modules:
        try:
            __import__(mod)
        except ImportError:
            issues.append(f"Missing: {mod}")
    
    return issues
```

### 6.2 타임아웃 메커니즘
```python
# 장시간 응답 없는 초기화 감지
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Initialization timeout!")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30초 타임아웃

try:
    init_database()
finally:
    signal.alarm(0)  # 타이머 취소
```

---

## 7. 결론 및 우선순위

| 우선순위 | 항목 | 영향도 | 수정 시간 |
|---------|------|------|---------|
| 🔴 P1 | run_tasks() 무한루프 방지 | 치명적 | 30분 |
| 🔴 P1 | on_closing() 강제 종료 로직 제거 | 치명적 | 20분 |
| 🔴 P1 | Spec 파일 동적 import 모듈 추가 | 높음 | 15분 |
| 🟠 P2 | DB 초기화 재시도 로직 추가 | 중간 | 20분 |
| 🟠 P2 | 에러 로깅 강화 | 중간 | 15분 |
| 🟡 P3 | hookspath 절대 경로 수정 | 낮음 | 10분 |

**총 수정 소요 시간**: 약 110분 (1시간 50분)

---

**다음 단계**: 위의 "긴급 조치" 섹션(4.1)을 순서대로 적용하고 테스트 체크리스트를 완료하세요.
