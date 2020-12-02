Dim FSObj
Set FSObj = CreateObject("Scripting.FileSystemObject")
path = FSObj.GetParentFolderName(WScript.ScriptFullName)
path = FSObj.GetParentFolderName(path)
Dim WShell
Set WShell = CreateObject("WScript.Shell")
WShell.Run chr(34) & path & "\binary.exe" & chr(34) & " --session-closed %NVIM_LISTEN_ADDRESS%", 0
Set WShell = Nothing
