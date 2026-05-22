Set WshShell = CreateObject("WScript.Shell")
Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")
Dim scriptDir
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "cmd /c """ & scriptDir & "\start.bat""", 0
Set WshShell = Nothing
Set fso = Nothing