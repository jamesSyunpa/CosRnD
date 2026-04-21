@echo off
chcp 65001 >nul
echo ================================================
echo Windows SmartScreen 차단 해제
echo ================================================
echo.
echo EXE 파일 차단 해제 중...
powershell -Command "Unblock-File -Path '..\dist\CoRQD_1.5.20251107.exe'"
echo.
echo 완료! 이제 프로그램을 실행해보세요.
echo.
echo ※ 주의: 파일을 복사하면 복사본도 차단 해제해야 합니다.
echo.
echo 복사한 파일 차단 해제 방법:
echo   1. 파일 우클릭 - 속성
echo   2. 하단의 "차단 해제" 체크
echo   3. 확인 클릭
echo.
pause
