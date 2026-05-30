@echo off
chcp 65001 > nul
set BACKUP_DIR=H:\Dev-PCE\Source\backend\db_backups
if not exist %BACKUP_DIR% mkdir %BACKUP_DIR%
copy "H:\Dev-PCE\Source\backend\db.sqlite3" "%BACKUP_DIR%\db_%date:~0,4%%date:~5,2%%date:~8,2%.sqlite3"
echo 备份完成：%date% %time%
pause