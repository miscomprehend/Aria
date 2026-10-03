$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

foreach ($command in @("node", "npm", "dotnet")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command is required. Install Node.js 22.12+ and the .NET 8 SDK, then rerun this script."
    }
}

$nodeVersion = (& node --version).Trim().TrimStart("v")
if ([version]$nodeVersion -lt [version]"22.12.0") {
    throw "Node.js 22.12 or later is required (found $nodeVersion)."
}

$sdkVersion = (& dotnet --version).Trim()
if ([int]($sdkVersion.Split(".")[0]) -lt 8) {
    throw ".NET SDK 8 or later is required (found $sdkVersion)."
}

$python = $null
$pythonArguments = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $python = "py"
        $pythonArguments = @("-3.11")
    }
}
if (-not $python -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $pythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    if ([version]$pythonVersion -ge [version]"3.11") {
        $python = "python"
    }
}
if (-not $python) {
    throw "Python 3.11 or later is required to run the Aria backend."
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python @pythonArguments -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the project Python environment."
    }
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not update pip in the project environment."
}
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Could not install Aria's Python dependencies."
}

& npm ci
if ($LASTEXITCODE -ne 0) {
    throw "Could not install Aria's desktop dependencies."
}

$env:ARIA_PYTHON = $venvPython
& npm start
if ($LASTEXITCODE -ne 0) {
    throw "Aria did not start successfully."
}
