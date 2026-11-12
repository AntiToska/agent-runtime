param(
    [ValidateSet('setup', 'check', 'test', 'format', 'run', 'build')]
    [string]$Task = 'check'
)

$ErrorActionPreference = 'Stop'
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$uvPath = if ($uvCommand) { $uvCommand.Source } else {
    Join-Path $env:USERPROFILE '.local\bin\uv.exe'
}
if (-not (Test-Path -LiteralPath $uvPath -PathType Leaf)) {
    throw 'uv was not found. Install uv and reopen the terminal, then retry.'
}

function Invoke-Uv {
    param([string[]]$UvArgs)
    & $uvPath @UvArgs
    if ($LASTEXITCODE -ne 0) {
        throw "uv $($UvArgs -join ' ') failed (exit $LASTEXITCODE)."
    }
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    Invoke-Uv -UvArgs @('sync', '--locked')
    switch ($Task) {
        'setup' { }
        'check' {
            Invoke-Uv -UvArgs @('run', '--locked', 'ruff', 'check', '.')
            Invoke-Uv -UvArgs @('run', '--locked', 'ruff', 'format', '--check', '.')
            Invoke-Uv -UvArgs @('run', '--locked', 'mypy')
            Invoke-Uv -UvArgs @('run', '--locked', 'pytest')
        }
        'test' { Invoke-Uv -UvArgs @('run', '--locked', 'pytest') }
        'format' { Invoke-Uv -UvArgs @('run', '--locked', 'ruff', 'format', '.') }
        'run' { Invoke-Uv -UvArgs @('run', '--locked', 'agent-runtime') }
        'build' { Invoke-Uv -UvArgs @('build') }
    }
}
finally {
    Pop-Location
}
