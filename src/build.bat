@echo off
setlocal

call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars32.bat"
if errorlevel 1 (
    echo Failed to initialize Visual Studio environment.
    pause
    exit /b 1
)

cl /nologo /LD /O2 /MT /EHsc /utf-8 VinylDuplicate.cpp /Fe:VinylDuplicate.asi /link /MACHINE:X86 user32.lib gdi32.lib
set ERR=%ERRORLEVEL%

if %ERR% equ 0 (
    echo.
    echo BUILD SUCCESSFUL: VinylDuplicate.asi created with /MT static CRT!
    del /q *.obj *.exp *.lib *.pdb *.ilk 2>nul
    echo Cleaned intermediate files.
) else (
    echo.
    echo BUILD FAILED with error code %ERR%
)

pause
endlocal