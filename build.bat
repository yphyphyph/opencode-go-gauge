@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo  GoUsage 打包脚本 (PyInstaller 单文件 exe)
echo ============================================
echo.

echo [1/3] 安装依赖...
pip install -q pywebview pyinstaller || goto :err

echo [2/3] 打包单文件 exe (无控制台窗口, logo 图标)...
pyinstaller --noconfirm --clean --onefile --noconsole --name GoUsage ^
  --add-data "app\web;app\web" ^
  --add-data "assets;assets" ^
  --icon assets\GoUsage.ico ^
  --collect-submodules webview ^
  --hidden-import clr ^
  --hidden-import pythonnet ^
  --hidden-import pystray ^
  entry.py || goto :err

echo [3/3] 完成!
echo.
echo 输出: dist\GoUsage.exe
echo 数据目录: 首次运行会在 exe 同目录创建 data\ 文件夹
echo.
pause
exit /b 0

:err
echo.
echo 打包失败, 请检查上方错误信息
pause
exit /b 1
