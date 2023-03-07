echo "Preparing to download nvim-ghost binary..."

$rootDir = Resolve-Path -Path ((Split-Path $myInvocation.MyCommand.Path) + "\..")
$version = Get-Content "$rootDir\binary_version"
$assetName = "nvim-ghost-win64.zip"
$assetPath = "$rootDir\$assetName"
$outFile = "$rootDir\nvim-ghost-binary.exe"

if (Test-Path $assetName) {
  rm "$assetName"
}

if (Test-Path $outFile) {
  echo "Binary still running"
  while (Test-Path $outFile) {
    try {
      rm "$outFile" -ErrorAction Stop
    }
    catch {
      echo "Please run ':call nvim_ghost#helper#kill_server()' in neovim"
      Start-Sleep -Seconds 1
    }
  }
}

echo "Downloading binary..."
Invoke-WebRequest `
  -uri "https://github.com/subnut/nvim-ghost.nvim/releases/download/$version/$assetName" `
  -OutFile ( New-Item -Path "$assetPath" -Force )
Expand-Archive -LiteralPath "$assetPath" -DestinationPath "$rootDir"
rm "$assetPath"

# vim: et sw=2 ts=2 sts=2
