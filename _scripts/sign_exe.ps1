# EXE 파일에 자체 서명 인증서로 디지털 서명하는 스크립트
# 사용법: .\sign_exe.ps1

$certName = "CoRQD Application"
$certPassword = "CoRQD2024!"
$exePath = "..\dist\CoRQD_1.5.20251107.exe"

Write-Host "=" * 60
Write-Host "CoRQD 실행 파일 디지털 서명"
Write-Host "=" * 60

# 1. 인증서 확인 또는 생성
$cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*$certName*" }

if (-not $cert) {
    Write-Host "`n[1단계] 자체 서명 인증서 생성 중..."
    
    # 자체 서명 인증서 생성
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=$certName, O=CoRQD, C=KR" `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -Provider "Microsoft Enhanced RSA and AES Cryptographic Provider" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears(5)
    
    Write-Host "  ✓ 인증서 생성 완료: $($cert.Thumbprint)"
    
    # 신뢰할 수 있는 루트 인증 기관에 추가
    Write-Host "`n[2단계] 인증서를 신뢰할 수 있는 루트로 추가 중..."
    Write-Host "  ※ 관리자 권한이 필요합니다."
    
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "LocalMachine")
    try {
        $store.Open("ReadWrite")
        $store.Add($cert)
        Write-Host "  ✓ 신뢰할 수 있는 루트에 추가됨"
    }
    catch {
        Write-Host "  ⚠ 경고: 관리자 권한으로 실행하지 않아 루트에 추가 실패"
        Write-Host "  → 'Windows 보호' 경고가 계속 나타날 수 있습니다."
        Write-Host "  → PowerShell을 관리자 권한으로 실행 후 다시 시도하세요."
    }
    finally {
        $store.Close()
    }
}
else {
    Write-Host "`n[1단계] 기존 인증서 발견"
    Write-Host "  Thumbprint: $($cert.Thumbprint)"
    Write-Host "  만료일: $($cert.NotAfter)"
}

# 3. EXE 파일 서명
Write-Host "`n[3단계] EXE 파일 서명 중..."

if (-not (Test-Path $exePath)) {
    Write-Host "  ✗ 오류: EXE 파일을 찾을 수 없습니다: $exePath"
    Write-Host "  → 빌드를 먼저 실행하세요."
    exit 1
}

try {
    # 타임스탬프 서버 (무료)
    $timestampServer = "http://timestamp.digicert.com"
    
    Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert -TimestampServer $timestampServer -HashAlgorithm SHA256
    
    Write-Host "  ✓ 서명 완료!"
    
    # 서명 확인
    $signature = Get-AuthenticodeSignature -FilePath $exePath
    Write-Host "`n[4단계] 서명 검증"
    Write-Host "  상태: $($signature.Status)"
    Write-Host "  서명자: $($signature.SignerCertificate.Subject)"
    
    if ($signature.Status -eq "Valid") {
        Write-Host "`n✅ 디지털 서명 성공!"
        Write-Host "`n※ 주의사항:"
        Write-Host "  - 자체 서명 인증서는 완전히 Windows 경고를 제거하지 못합니다."
        Write-Host "  - 공식 코드 서명 인증서 구매 시 경고가 완전히 제거됩니다."
        Write-Host "  - 현재 PC에서는 경고가 줄어들 수 있습니다."
    }
    else {
        Write-Host "`n⚠ 서명 상태: $($signature.Status)"
    }
}
catch {
    Write-Host "  ✗ 서명 실패: $_"
    exit 1
}

Write-Host "`n" + ("=" * 60)
