set http_proxy=http://127.0.0.1:50046
set https_proxy=http://127.0.0.1:50046
appcfg.py update ..\blog --noauth_local_webserver --no_cookies
pause