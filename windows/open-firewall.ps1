<#
.SYNOPSIS
    Opens the Windows Firewall for the MLBB Draft AI receiver.

.DESCRIPTION
    Creates two inbound rules:
      * TCP 8765  - the iPhone streams screen frames here
      * TCP 8080  - the dashboard (browser) connects here

    The rules are restricted to the Private network profile only, so they
    do not open the ports on public/corporate networks.

    Run from an ELEVATED PowerShell (right-click -> Run as administrator).
    Requires Administrator rights; no third-party tools needed.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\open-firewall.ps1

.EXAMPLE
    .\open-firewall.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$RulePrefix = "MLBB Draft AI"
$PortRules  = @(
    @{ Name = "$RulePrefix - Ingest (frames)"; Port = 8765; Purpose = "iPhone screen frames" },
    @{ Name = "$RulePrefix - Dashboard";        Port = 8080; Purpose = "web dashboard" }
)

function Remove-Rules {
    foreach ($r in $PortRules) {
        $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
        if ($existing) {
            Remove-NetFirewallRule -DisplayName $r.Name
            Write-Host "Removed rule: $($r.Name)" -ForegroundColor Yellow
        }
    }
    Write-Host "Firewall rules removed." -ForegroundColor Green
}

if ($Remove) {
    Remove-Rules
    exit 0
}

# Must be elevated to create firewall rules.
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Error "Administrator rights required. Right-click PowerShell and 'Run as administrator', then run this script again."
    exit 1
}

Write-Host "Adding firewall rules for Private networks only..." -ForegroundColor Cyan

foreach ($r in $PortRules) {
    # Remove any stale rule with the same name so re-running is safe.
    Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction SilentlyContinue

    New-NetFirewallRule `
        -DisplayName $r.Name `
        -Description "MLBB Draft AI - $($r.Purpose)" `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $r.Port `
        -Profile Private `
        -Enabled True | Out-Null

    Write-Host ("  + {0}  (TCP {1})" -f $r.Name, $r.Port) -ForegroundColor Green
}

Write-Host ""
Write-Host "Firewall is ready." -ForegroundColor Green
Write-Host "Open the dashboard at: http://<this-PC-IP>:8080/"
Write-Host ""
Write-Host "To undo, run: .\open-firewall.ps1 -Remove"
