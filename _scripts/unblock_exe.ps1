# Windows SmartScreen 차단 해제 스크립트
# 사용법: .\unblock_exe.ps1

$exePath = "..\dist\CoRQD_1.5.20251107.exe"

Write-Host "=" * 60
Write-Host "Windows SmartScreen 차단 해제"
Write-Host "=" * 60

if (-not (Test-Path $exePath)) {
    Write-Host "`n✗ 오류: EXE 파일을 찾을 수 없습니다: $exePath"
    exit 1
}

Write-Host "`n[1단계] 현재 파일 상태 확인..."
$file = Get-Item $exePath
$zone = Get-Content "$exePath`:Zone.Identifier" -ErrorAction SilentlyContinue

if ($zone) {
    Write-Host "  ⚠ 파일이 차단됨 (인터넷에서 다운로드된 것으로 표시)"
    Write-Host "  Zone 정보: $zone"
} else {
    Write-Host "  ✓ 파일이 차단되지 않음"
}

Write-Host "`n[2단계] 파일 차단 해제 중..."
try {
    Unblock-File -Path $exePath
    Write-Host "  ✓ 차단 해제 완료!"
    
    # 검증
    $zoneAfter = Get-Content "$exePath`:Zone.Identifier" -ErrorAction SilentlyContinue
    if (-not $zoneAfter) {
        Write-Host "  ✓ Zone 정보 제거됨"
    }
    
    Write-Host "`n✅ 성공! 이제 파일을 실행해보세요."
    Write-Host "`n※ 파란색 경고로 변경되거나 경고가 사라질 수 있습니다."
    
} catch {
    Write-Host "  ✗ 차단 해제 실패: $_"
    Write-Host "`n대안: 파일 속성에서 수동 해제"
    Write-Host "  1. 파일 우클릭 -> 속성"
    Write-Host "  2. 일반 탭 하단의 '차단 해제' 체크박스 선택"
    Write-Host "  3. 확인 클릭"
}

Write-Host ""
Write-Host ("=" * 60)
