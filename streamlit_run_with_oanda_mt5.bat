@echo on

python -m streamlit run %~dp0app\main.py ^
  --logger.level=debug ^
  -- ^
  --retry-count=5 ^
  --sqlite3="%~dp0db.sqlite3"
