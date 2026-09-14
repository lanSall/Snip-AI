Set WshShell = CreateObject("WScript.Shell")
' Run with pythonw so no console window appears.
WshShell.Run "pythonw -m snipai run", 0, False
