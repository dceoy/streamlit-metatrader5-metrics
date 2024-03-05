Set-PSDebug -Trace 1

try {
  python -V
  python -m pip install -U --no-cache-dir -r $PSScriptRoot\requirements.txt
  python -m streamlit run $PSScriptRoot\app\main.py --logger.level=info `
    -- --retry-count=5 --sqlite3="$PSScriptRoot\db.sqlite3"
}
finally {
  Set-PSDebug -Trace 0
}

. $PSScriptRoot\run_mteor.ps1
