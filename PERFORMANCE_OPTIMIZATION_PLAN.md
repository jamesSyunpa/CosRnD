# 프로그램 성능 분석 및 최적화 보고서

## 1. 현상 분석 (Performance Analysis)

프로그램의 시작 속도 저하와 GUI 끊김(Stuttering) 현상의 주요 원인은 **동기식(Synchronous) 데이터 로딩**과 **초기화 시점의 과부하**에 있었습니다.

### 1.1. 초기화 시점의 병목 (Bottleneck at Startup)
`main.py`의 `setup_main_ui` 메서드에서 애플리케이션의 모든 주요 화면(Frame)을 한 번에 초기화하고 있었습니다.
```python
# main.py (이전 구조)
self.frames[FRAME_HOME] = HomeFrame(...)
self.frames[FRAME_SETTINGS] = SettingsManagementFrame(...)
self.frames[FRAME_DATA] = DataManagementFrame(...) # 여기서 데이터 로딩 발생
self.frames[FRAME_DOCUMENT] = DocumentManagementFrame(...)
...
```
사용자가 아직 방문하지 않은 화면(`DataManagementFrame` 등)까지 프로그램 시작 시점에 모두 생성하며, 각 프레임의 `__init__`에서 DB 데이터를 조회하여 메모리에 적재하는 작업이 메인 스레드에서 수행되었습니다.

### 1.2. 데이터 관리 프레임의 부하 (Data Management Load)
`modules/data_management.py`와 `modules/material_management.py`는 초기화(`__init__`) 즉시 대량의 데이터를 로딩했습니다.
- DB에서 전체 데이터를 조회(`SELECT *`)합니다.
- 조회된 데이터를 `Treeview` 위젯에 하나씩 `insert` 합니다.
- 이 과정이 메인 스레드(GUI 스레드)에서 실행되므로, 데이터 양이 많을수록 화면이 멈추거나 "따발총 쏘듯이" 위젯이 그려지는 현상이 발생했습니다.

### 1.3. 홈 화면의 부하
`modules/home_frame.py` 역시 초기화 시 `load_recent_material_changes()`를 동기적으로 호출하여, 시작 시 체감 딜레이를 유발했습니다.

---

## 2. 최적화 적용 내역 (Optimization Implemented)

미래지향적이고 반응성이 뛰어난 애플리케이션으로 전환하기 위해 다음 기술들이 적용되었습니다.

### 2.1. 지연 로딩 (Lazy Loading) 적용 [완료]
프로그램 시작 시에는 **홈 화면(HomeFrame)**만 생성하고, 나머지 무거운 화면들은 사용자가 메뉴를 클릭했을 때 생성하도록 변경했습니다.

**적용된 로직:**
1. `main.py`의 `setup_main_ui`에서는 `HomeFrame`만 생성.
2. `select_frame_by_name` 메서드에서 요청된 프레임이 `self.frames`에 없으면 그때 생성(Instantiate)하고 표시.
3. 로딩 커서(`wait` cursor)를 도입하여 프레임 생성 중임을 사용자에게 알림.

### 2.2. 비동기 데이터 로딩 (Asynchronous Data Loading) 적용 [완료]
데이터베이스 조회와 UI 갱신을 분리하여 GUI 멈춤 현상을 제거했습니다.

**적용 대상:**
- **데이터 관리 (DataManagementFrame):** 사용자 관리(`load_users`) 및 거래처 관리(`load_clients`)
- **원료 관리 (MaterialManagementFrame):** 원료 목록 조회(`load_materials`, `refresh_data`) 및 거래처 콤보박스 로딩
- **홈 화면 (HomeFrame):** 최근 변경 이력 조회(`load_recent_material_changes`)

**구현 방식:**
- `threading` 모듈을 사용하여 DB 조회는 백그라운드 스레드에서 수행.
- 조회 완료 후 `after()` 메서드를 통해 메인 스레드에서 UI를 안전하게 갱신.
- 대량 데이터의 경우 `Treeview` 삽입을 청크(Chunk) 단위로 나누어 UI 프리징 방지.

### 2.3. 사용자 경험 개선
- 데이터 로딩 중 UI가 멈추지 않아 다른 탭으로 이동하거나 작업을 계속할 수 있음.
- 프로그램 시작 시간이 획기적으로 단축됨 (모든 데이터를 미리 로드하지 않음).

---

## 3. 향후 유지보수 가이드 (Maintenance Guide)

새로운 기능을 추가할 때 성능을 유지하기 위해 다음 규칙을 준수하십시오.

1. **무거운 작업은 스레드로:** DB 조회, 파일 I/O, 네트워크 요청 등 0.1초 이상 걸릴 수 있는 작업은 반드시 `threading.Thread`를 사용하십시오.
2. **UI 갱신은 메인 스레드에서:** 스레드 내부에서 직접 UI를 수정하지 말고, `self.after(0, callback)` 패턴을 사용하십시오.
3. **지연 로딩 유지:** `main.py`에 새로운 탭을 추가할 때, `setup_main_ui`에 미리 추가하지 말고 `select_frame_by_name`의 분기문에 추가하십시오.
