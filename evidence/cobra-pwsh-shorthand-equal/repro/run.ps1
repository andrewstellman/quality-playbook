# cobra BUG-018 on the Mac: load the generated PowerShell completion for prog, then ask PowerShell's own completer
# (TabExpansion2, what TAB uses) for "prog get -o=" and, as a control, "prog get --output=".
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$arch = if ((uname -m) -eq "arm64") { "arm64" } else { "amd64" }
Copy-Item "$here/prog-darwin-$arch" "$here/prog" -Force
chmod +x "$here/prog"
$env:PATH = "$here" + [IO.Path]::PathSeparator + $env:PATH
"pwsh $($PSVersionTable.PSVersion); prog built from cobra adbc8813 (darwin-$arch)"
& prog completion powershell | Out-String | Invoke-Expression
foreach ($line in @("prog get -o=", "prog get --output=")) {
  $r = TabExpansion2 -inputScript $line -cursorColumn $line.Length
  "{0,-20} -> {1}" -f $line, (($r.CompletionMatches | ForEach-Object CompletionText) -join ", ")
}
