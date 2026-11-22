# cobra BUG-018 fix check on the Mac: the same test as run.ps1, with prog built from cobra main + the one-line fix.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$arch = if ((uname -m) -eq "arm64") { "arm64" } else { "amd64" }
Copy-Item "$here/prog-fixed-darwin-$arch" "$here/prog" -Force
chmod +x "$here/prog"
$env:PATH = "$here" + [IO.Path]::PathSeparator + $env:PATH
"pwsh $($PSVersionTable.PSVersion); prog built from cobra main adbc8813 + fix (darwin-$arch)"
& prog completion powershell | Out-String | Invoke-Expression
foreach ($line in @("prog get -o=", "prog get --output=", "prog get -o ", "prog get --output ")) {
  $r = TabExpansion2 -inputScript $line -cursorColumn $line.Length
  "{0,-20} -> {1}" -f $line, (($r.CompletionMatches | ForEach-Object CompletionText) -join ", ")
}
