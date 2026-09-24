@echo off
set FLASK_APP=wsgi.py
set FLASK_DEBUG=1
flask run --debug
