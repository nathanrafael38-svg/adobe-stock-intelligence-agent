' Runs a .bat completely hidden (no console window). Usage: wscript.exe run_hidden.vbs "<path to .bat>"
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count > 0 Then
  sh.Run "cmd /c """ & WScript.Arguments(0) & """", 0, True
End If
