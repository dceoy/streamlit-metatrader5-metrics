Set-PSDebug -Trace 1

try {
  python -V
  python -m pip install -U --no-cache-dir $PSScriptRoot
  python -m streamlit run $PSScriptRoot\app\main.py `
    --logger.level=info `
    --server.headless true `
    -- `
    --retry-count=5 `
    --sqlite3="$PSScriptRoot\db.sqlite3"
}
finally {
  Set-PSDebug -Trace 0
}
