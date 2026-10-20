# Set (or reset) the app's password - on this PC only, on purpose: there's no sign-up page someone else on the Wi-Fi
# could get to first, and a lost password or phone is fixed here, where only you can.
#
#   .\set-password.ps1                         # set or change the password (asked twice, not shown)
#   .\set-password.ps1 -ResetAuthenticator     # ...and turn off the authenticator app (lost or new phone)
#   .\set-password.ps1 -SignOutEverywhere      # ...and sign out every device (one was lost or stolen)
#
# Runs `python -m app.auth set-password` inside this copy's API container (api/app/auth.py). ASCII only.
param([switch]$ResetAuthenticator, [switch]$SignOutEverywhere)

. "$PSScriptRoot\scripts\common.ps1"
if (-not (Test-Healthy $ApiContainer)) {
    Write-Host "$ApiContainer isn't running. Start the app first (.\start.ps1, or .\dev.ps1 for the dev copy)." -ForegroundColor Red
    exit 1
}
$cmd = @('python', '-m', 'app.auth', 'set-password')
if ($ResetAuthenticator) { $cmd += '--reset-authenticator' }
if ($SignOutEverywhere) { $cmd += '--sign-out-everywhere' }
Write-Host "Setting the password for the $AppEnv copy. At least 12 characters (a few unrelated words is strong)." -ForegroundColor Cyan
docker exec -it $ApiContainer @cmd
exit $LASTEXITCODE
