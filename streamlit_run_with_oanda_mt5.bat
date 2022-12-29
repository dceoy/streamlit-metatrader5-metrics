@echo on

python -m streamlit run app.py -- ^
  --debug ^
  --mt5-exe="C:\Program Files\OANDA MetaTrader 5\terminal64.exe" ^
  --retry-count=5 ^
  --sqlite3-path="%~dp0db.sqlite3"
