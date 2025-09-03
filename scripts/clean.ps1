Write-Host "Cleaning __pycache__ and *.pyc..."
Get-ChildItem -Recurse -Directory -Filter __pycache__ | ForEach-Object { Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $_.FullName }
Get-ChildItem -Recurse -Filter *.pyc | ForEach-Object { Remove-Item -Force -ErrorAction SilentlyContinue $_.FullName }
Write-Host "Done."

