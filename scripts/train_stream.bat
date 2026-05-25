@echo off
title NP-DNA Streaming Training
cd /d "%~dp0.."
echo.
echo   ================================
echo    NP-DNA Streaming Training
echo   ================================
echo.
echo   Config:  atulya_seed
echo   Data:    tantra\data\ (all JSONL files)
echo   Mode:    streaming (no memory limit)
echo.
echo   Training started at %date% %time%
echo   Close this window to stop training.
echo.
echo   ================================
echo.
python -m tantra.training.npdna_train ^
    --config atulya_seed ^
    --steps 50000 ^
    --data-dir tantra\data ^
    --stream ^
    --tag streaming_run ^
    --auto-resume ^
    --device cpu ^
    --pack ^
    --log-every 50
echo.
echo   Training finished at %date% %time%
pause
