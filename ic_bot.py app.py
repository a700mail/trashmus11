[1mdiff --git a/ic_bot.py b/ic_bot.py[m
[1mdeleted file mode 100644[m
[1mindex 80eecf2..0000000[m
[1m--- a/ic_bot.py[m
[1m+++ /dev/null[m
[36m@@ -1,5 +0,0 @@[m
[31m-[33mc0c0371[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m, [m[1;31morigin/main[m[33m, [m[1;31morigin/HEAD[m[33m)[m Remove payment systems and simplify bot configuration - Removed all payment-related environment variables - Updated render.yaml to only require BOT_TOKEN - Simplified env_template.txt - Updated documentation to remove payment references - Bot now works without payment systems[m
[31m-[33m8a615ea[m Initial commit: Telegram Music Bot with Render deployment support - Added main bot functionality (music_bot.py) - Added Flask web app for Render (app.py) - Added Render configuration files (render.yaml, Procfile, runtime.txt) - Added comprehensive documentation (RENDER_DEPLOYMENT.md, QUICK_START_RENDER.md) - Added requirements.txt with Flask dependency - Added .gitignore for Python projects - Updated README.md with Render deployment info[m
[31m-[33md89b9e3[m Remove all files[m
[31m-[33m05ff24f[m Fix: web_service.py is now the main file with Flask + bot integration[m
[31m-[33m40af30b[m Create web_service.py and update app.py to run bot in separate process[m
