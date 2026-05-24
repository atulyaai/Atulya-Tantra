@echo off
title NP-DNA Training
cd /d "%~dp0.."
echo.
echo   ============================
echo    NP-DNA Training Window
echo   ============================
echo.
echo   Config: atulya_seed
echo   Data:   tantra\training\datasets\identity.json
echo.
echo   Training started at %date% %time%
echo   Close this window to stop training.
echo.
echo   ============================
echo.
    python -m tantra.training.npdna_train ^
    --config atulya_seed ^
    --steps 1000 ^
    --device cpu ^
    --pack ^
    --log-every 10
echo.
echo   Training finished at %date% %time%
pause
