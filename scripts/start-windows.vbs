Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
scriptsDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(scriptsDir)
pythonw = root & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonw) Then
  pythonw = "pythonw"
End If
sh.CurrentDirectory = root
' Run with pythonw so no console window appears. Double-click Start.bat first.
sh.Run """" & pythonw & """ -m snipai run", 0, False
