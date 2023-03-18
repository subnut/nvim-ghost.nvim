Write-Output "Preparing to download nvim-ghost binary..."
Set-Location (Resolve-Path -Path ((Split-Path $myInvocation.MyCommand.Path) + "\.."))

$version = Get-Content "binary_version"
$asset = "nvim-ghost-win64.zip"
$binary = "nvim-ghost-binary.exe"

# Delete previous partial downloads
Remove-Item -ErrorAction:Ignore "$asset"

# Delete current binary
Remove-Item -ErrorAction:Ignore "$binary"
Remove-Item -ErrorAction:Ignore "$binary.version"
if (Test-Path $binary) {
  echo "Binary still running"
  while (Test-Path $binary) {
    try {
      Remove-Item -ErrorAction:Stop "$binary"
    }
    catch {
      echo "Please run ':call nvim_ghost#helper#kill_server()' in neovim"
      Start-Sleep -Seconds 1
    }
  }
}

echo "Downloading binary..."
Invoke-WebRequest `
  -uri "https://github.com/subnut/nvim-ghost.nvim/releases/download/$version/$asset" `
  -OutFile "$asset"
Expand-Archive "$asset"
Remove-Item "$asset"

# vim: et sw=2 ts=2 sts=2
