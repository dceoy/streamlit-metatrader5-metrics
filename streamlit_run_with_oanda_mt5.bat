@echo on

python -m pip install -U --no-cache-dir ^
  -r %~dp0requirements.txt
python -m streamlit run %~dp0app\main.py ^
  --logger.level=info ^
  -- ^
  --retry-count=5 ^
  --sqlite3="%~dp0db.sqlite3"
