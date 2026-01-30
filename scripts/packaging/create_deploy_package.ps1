<# 
.SYNOPSIS
    Creates a minimal deployment package for WorkDataHub intranet migration verification.
.DESCRIPTION
    Generates a ZIP archive containing only essential files for environment validation,
    excluding development dependencies, caches, and large data files.
.PARAMETER OutputPath
    Path for the output ZIP file. Defaults to wdh-deploy-pack.zip in current directory.
.EXAMPLE
    .\create_deploy_package.ps1
    .\create_deploy_package.ps1 -OutputPath "D:\Deploy\wdh-v1.zip"
#>
param(
    [string]$OutputPath = "wdh-deploy-pack.zip"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "Creating WorkDataHub deployment package..." -ForegroundColor Cyan

# Temp staging directory
$TempDir = Join-Path $env:TEMP "wdh-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

try {
    # Define files/directories to include
    $IncludeItems = @(
        "src",
        "config",
        "io/schema/migrations",
        "pyproject.toml",
        "uv.lock",
        "alembic.ini",
        ".env.example",
        ".python-version",
        "docs/runbooks/intranet-migration-verification.md"
    )

    # Define exclusion patterns (directories and file patterns to remove after copy)
    $ExcludePatterns = @(
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".coverage",
        "*.pyc",
        "*.pyo"
    )

    foreach ($item in $IncludeItems) {
        $SourcePath = Join-Path $ProjectRoot $item
        $DestPath = Join-Path $TempDir $item
        
        if (Test-Path $SourcePath) {
            $ParentDir = Split-Path -Parent $DestPath
            if (-not (Test-Path $ParentDir)) {
                New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null
            }
            
            if (Test-Path $SourcePath -PathType Container) {
                # Copy directory first
                Copy-Item -Path $SourcePath -Destination $DestPath -Recurse -Force
                
                # Clean up cache directories (by name)
                $CacheDirs = @("__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache")
                foreach ($dirName in $CacheDirs) {
                    Get-ChildItem -Path $DestPath -Recurse -Directory -Force -ErrorAction SilentlyContinue | 
                        Where-Object { $_.Name -eq $dirName } |
                        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                }
                
                # Clean up cache files (by extension)
                Get-ChildItem -Path $DestPath -Recurse -File -Force -ErrorAction SilentlyContinue |
                    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
                    Remove-Item -Force -ErrorAction SilentlyContinue
            } else {
                Copy-Item -Path $SourcePath -Destination $DestPath -Force
            }
            Write-Host "  + $item" -ForegroundColor Green
        } else {
            Write-Host "  - $item (not found, skipped)" -ForegroundColor Yellow
        }
    }

    # Create README for the package
    $ReadmeContent = @"
# WorkDataHub Deployment Package

Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

## Quick Start

1. Extract this archive to your target directory
2. Copy `.env.example` to `.wdh_env` and configure database connection
3. Install uv (if not available): pip install uv
4. Run: uv sync
5. Follow verification steps in docs/runbooks/intranet-migration-verification.md

## Included Files

- src/ - Source code
- config/ - Configuration mappings
- io/schema/migrations/ - Database migrations
- pyproject.toml + uv.lock - Python dependencies
- alembic.ini - Migration config
- .env.example - Environment template
"@
    $ReadmeContent | Out-File -FilePath (Join-Path $TempDir "README.md") -Encoding utf8

    # Create ZIP archive
    $OutputFullPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $ProjectRoot $OutputPath }
    
    if (Test-Path $OutputFullPath) {
        Remove-Item $OutputFullPath -Force
    }
    
    Compress-Archive -Path "$TempDir\*" -DestinationPath $OutputFullPath -Force
    
    $ZipSize = (Get-Item $OutputFullPath).Length / 1MB
    Write-Host "`nPackage created: $OutputFullPath" -ForegroundColor Cyan
    Write-Host "Size: $([math]::Round($ZipSize, 2)) MB" -ForegroundColor Cyan

} finally {
    # Cleanup temp directory
    if (Test-Path $TempDir) {
        Remove-Item $TempDir -Recurse -Force
    }
}

Write-Host "`nDone! Transfer the package to the intranet and follow the runbook." -ForegroundColor Green
