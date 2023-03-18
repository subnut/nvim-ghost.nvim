Write-Output "Preparing to download nvim-ghost binary"
Set-Location (Resolve-Path -Path ((Split-Path $myInvocation.MyCommand.Path) + "\.."))

$version  = Get-Content "binary_version"
$archive  = "nvim-ghost-win64.zip"
$binary   = "nvim-ghost-binary.exe"

Remove-Item -ErrorAction:Ignore "$archive"
Remove-Item -ErrorAction:Ignore "$binary"
Remove-Item -ErrorAction:Ignore "$binary.version"

if (Test-Path "$binary") {
  Write-Output "Binary still running"
  Write-Output "Please run ':call nvim_ghost#helper#kill_server()' in neovim"
  while (Test-Path "$binary") {
    try { Remove-Item -ErrorAction:Stop "$binary" }
    catch { Start-Sleep -Seconds 1 }
  }
}

Write-Output "Downloading binary $version"
Invoke-WebRequest `
  -uri "https://github.com/subnut/nvim-ghost.nvim/releases/download/$version/$archive" `
  -OutFile "$archive"
Expand-Archive "$archive" -DestinationPath .
Remove-Item "$archive"

# vim: et sw=2 ts=2 sts=2
