# Windows SmartScreen 경고 우회 방법

## 문제 상황
처음 실행 시 "Windows에서 PC 보호" 메시지가 표시되며, "실행 안 함" 또는 "추가 정보" 버튼만 보입니다.

## 해결 방법

### 방법 1: 즉시 실행 (권장)

1. **"추가 정보"** 클릭
2. 나타나는 **"실행"** 버튼 클릭
3. 프로그램 정상 실행

![SmartScreen 우회](https://docs.microsoft.com/ko-kr/windows/security/threat-protection/windows-defender-smartscreen/images/smartscreen-run-anyway.png)

---

### 방법 2: 디지털 서명 (개발자용)

빌드 후 PowerShell을 **관리자 권한**으로 실행:

```powershell
cd "C:\Users\neon5\Desktop\RnD_플랫폼\_scripts"
Set-ExecutionPolicy Bypass -Scope Process -Force
.\sign_exe.ps1
```

**효과:**
- 자체 서명 인증서로 EXE 파일에 디지털 서명
- 현재 PC에서 경고가 줄어들 수 있음
- 다른 PC에서는 여전히 경고 표시됨

**완전한 해결:**
- 공식 코드 서명 인증서 구매 필요 (연간 약 30-50만원)
- Comodo, DigiCert, GlobalSign 등

---

### 방법 3: Windows Defender SmartScreen 비활성화 (권장하지 않음)

1. **Windows 보안** 열기
2. **앱 및 브라우저 제어** → **평판 기반 보호 설정**
3. **앱 확인** 끄기

⚠️ 보안 위험이 있으므로 권장하지 않습니다.

---

## 왜 이런 경고가 나타나나요?

- **새로운 실행 파일**: Microsoft가 이 파일을 충분히 검증하지 못했습니다.
- **디지털 서명 없음**: 공식 코드 서명 인증서가 없습니다.
- **다운로드 수 부족**: 많은 사용자가 다운로드하지 않았습니다.

---

## 사용자 배포 시 안내 문구

```
※ 최초 실행 시 Windows 보안 경고가 나타날 수 있습니다.
   "추가 정보" → "실행" 클릭으로 정상 실행 가능합니다.
   
   본 프로그램은 안전하며, 악성코드가 없음을 보증합니다.
```

---

## 참고 자료
- [Microsoft SmartScreen 문서](https://docs.microsoft.com/ko-kr/windows/security/threat-protection/windows-defender-smartscreen/windows-defender-smartscreen-overview)
- [코드 서명 인증서 안내](https://docs.microsoft.com/ko-kr/windows-hardware/drivers/dashboard/code-signing-cert-manage)
