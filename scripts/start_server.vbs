Dim FSObj
Set FSObj = CreateObject("Scripting.FileSystemObject")
path = FSObj.GetParentFolderName(WScript.ScriptFullName)
path = FSObj.GetParentFolderName(path)
Dim WShell
Set WShell = CreateObject("WScript.Shell")
WScript.Echo(path & "\binary.exe --start-server --persist")
WShell.Run chr(34) & path & "\binary.exe" & chr(34) & " --start-server --persist", 0
Set WShell = Nothing
