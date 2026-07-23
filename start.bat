@echo off
chcp 65001 >nul
title 初中跨学科教学评一体化平台

:: ============================================
:: 一键启动脚本 (Windows)
:: 启动后端 (FastAPI / uvicorn) + 前端 (Vite)
:: ============================================

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%project\backend
set FRONTEND_DIR=%ROOT_DIR%project\frontend
set BACKEND_PORT=2358
set FRONTEND_PORT=1800

echo ============================================
echo  初中跨学科教学评一体化平台 - 一键启动
echo ============================================
echo.

:: ---------- 后端 ----------
echo [1/2] 启动后端 (FastAPI) —— 端口 %BACKEND_PORT%

if not exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    echo [错误] 后端虚拟环境不存在，请先执行:
    echo        cd project\backend ^&^& python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: 清理旧日志
del "%BACKEND_DIR%\backend_uvicorn.log" 2>nul

:: 后台启动后端（直接用 python 调用 uvicorn，不走 activate，避免编码警告）
start "backend" /B /D "%BACKEND_DIR%" "%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port %BACKEND_PORT% --log-level info 1>"%BACKEND_DIR%\backend_uvicorn.log" 2>&1
echo [后端] 已启动，日志: project\backend\backend_uvicorn.log

:: ---------- 前端 ----------
echo [2/2] 启动前端 (Vite) —— 端口 %FRONTEND_PORT%

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [前端] 正在安装依赖（首次运行需要等待）...
    cd /d "%FRONTEND_DIR%" ^&^& call npm install
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
    cd /d "%ROOT_DIR%"
)

del "%FRONTEND_DIR%\frontend_vite.log" 2>nul

:: 后台启动前端
start "frontend" /B cmd /c "cd /d "%FRONTEND_DIR%" ^&^& npx vite --port %FRONTEND_PORT% 1>"%FRONTEND_DIR%\frontend_vite.log" 2>&1"
echo [前端] 已启动，日志: project\frontend\frontend_vite.log

:: ---------- 完成 ----------
echo.
echo ============================================
echo  启动完成!
echo.
echo  前端地址:  http://localhost:%FRONTEND_PORT%
echo  后端地址:  http://localhost:%BACKEND_PORT%
echo  API 文档:  http://localhost:%BACKEND_PORT%/docs
echo.
echo  查看日志:
echo    后端日志: type project\backend\backend_uvicorn.log
echo    前端日志: type project\frontend\frontend_vite.log
echo.
echo  停止服务: 关闭此窗口 或 Ctrl+C
echo ============================================

:: 等 2 秒后自动打开浏览器
timeout /t 2 /nobreak >nul
start http://localhost:%FRONTEND_PORT%
