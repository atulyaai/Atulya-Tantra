@echo off
title NP-DNA Training (Background)
cd /d "%~dp0.."
echo.
echo   ============================
echo    NP-DNA Background Training
echo   ============================
echo.
echo   Config: atulya_seed
echo   Data:   tantra\training\datasets\identity.json
echo.
echo   Logging to: outputs\training_bg.log
echo.
echo   Training started at %date% %time%
echo.
mkdir outputs 2>nul
    python -m tantra.training.npdna_train ^
    --config atulya_seed ^
    --steps 1000 ^
    --device cpu ^
    --pack ^
    --log-every 10 ^
    > outputs\training_bg.log 2>&1
echo.
echo   Training finished at %date% %time% >> outputs\training_bg.log 2>&1
exit /b
