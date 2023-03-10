@echo off
setlocal
echo @echo off > "%~dp0/deactivate_conanrunenv-release-x86_64.bat"
echo echo Restoring environment >> "%~dp0/deactivate_conanrunenv-release-x86_64.bat"
for %%v in (PYTHONPATH PATH TK_LIBRARY TCL_ROOT TCL_LIBRARY TCLSH) do (
    set foundenvvar=
    for /f "delims== tokens=1,2" %%a in ('set') do (
        if /I "%%a" == "%%v" (
            echo set "%%a=%%b">> "%~dp0/deactivate_conanrunenv-release-x86_64.bat"
            set foundenvvar=1
        )
    )
    if not defined foundenvvar (
        echo set %%v=>> "%~dp0/deactivate_conanrunenv-release-x86_64.bat"
    )
)
endlocal


set "PYTHONPATH=%PYTHONPATH%;C:\.conan\473d56\1\lib"
set "PATH=C:\.conan\b1abf7\1\bin;C:\.conan\5fbda0\1\bin;C:\.conan\3b3209\1\bin;C:\.conan\e847a3\1\bin;C:\.conan\caef4d\1\bin;C:\.conan\b206d1\1\bin;C:\.conan\d9d475\1\bin;C:\.conan\6a9c75\1\bin;%PATH%"
set "TK_LIBRARY=C:/.conan/d9d475/1/lib/tk8.6"
set "TCL_ROOT=C:/.conan/d9d475/1"
set "TCL_LIBRARY=C:\.conan\6a9c75\1\lib\tcl8.6"
set "TCLSH=C:\.conan\6a9c75\1\bin\tclsh86tsx.exe"