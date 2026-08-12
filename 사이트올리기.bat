@echo off
cd /d "%~dp0"
chcp 949 >nul
title 유성현황 사이트 올리기
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PY=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PY%" set PY=python

echo ==========================================================
echo   유성현황을 새로 만들어서 인터넷 사이트에 반영합니다.
echo ==========================================================
echo.

rem ── 처음 한 번만: 깃허브 저장소 연결 ──
git remote get-url origin >nul 2>&1
if not errorlevel 1 goto BUILD

echo [처음 설정] 깃허브 저장소를 아직 연결하지 않았습니다.
echo.
echo   github.com 에서 저장소를 먼저 만들어 주세요.
echo    - 이름은 meteor 정도가 주소가 짧아서 좋습니다
echo    - Public 을 고르고, 아래 체크박스는 아무것도 건드리지 말고 Create
echo.
set /p GHUSER="깃허브 사용자명(아이디): "
set /p GHREPO="저장소 이름 (엔터만 치면 meteor): "
if "%GHREPO%"=="" set GHREPO=meteor
git remote add origin https://github.com/%GHUSER%/%GHREPO%.git
echo.
echo   연결했습니다 : https://github.com/%GHUSER%/%GHREPO%
echo.

:BUILD
echo [1/3] 최신 데이터로 다시 만드는 중...
"%PY%" "유성현황.py" %* --noopen
if errorlevel 1 goto FAIL

echo.
echo [2/3] 변경사항 기록 중...
git add -A
git diff --cached --quiet
if not errorlevel 1 goto NOCHANGE
git commit -q -m "유성현황 갱신"

echo.
echo [3/3] 인터넷에 올리는 중...
echo   (자동 갱신분이 있으면 먼저 받아옵니다)
git pull --rebase --autostash -q
echo   (처음이면 브라우저가 열립니다 - 깃허브 로그인하고 승인해 주세요)
git push -u origin main
if errorlevel 1 goto PUSHFAIL
goto DONE

:NOCHANGE
echo   바뀐 내용이 없어 그대로 둡니다.

:DONE
echo.
echo ==========================================================
echo   반영 완료.
git remote get-url origin
echo.
echo   사이트 주소는 저장소 Settings - Pages 에서 확인하세요.
echo   보통 1~2분 뒤부터 바뀐 내용이 보입니다.
echo ==========================================================
pause
exit /b

:PUSHFAIL
echo.
echo [실패] 인터넷에 올리지 못했습니다.
echo   - 깃허브에서 저장소를 먼저 만드셨는지 확인해 주세요.
echo   - 사용자명이나 저장소 이름을 잘못 넣었다면 아래로 고칠 수 있습니다:
echo       git remote set-url origin https://github.com/사용자명/저장소이름.git
pause
exit /b

:FAIL
echo.
echo [실패] 현황판을 만들지 못했습니다. 인터넷 연결을 확인해 주세요.
pause
exit /b
