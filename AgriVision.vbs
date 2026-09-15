Option Explicit
' Double-click launcher: starts AgriVision without a console window.
' If pyw is missing, falls back to AgriVision.bat so errors stay visible.
Dim fso, sh, root
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("Wscript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root

On Error Resume Next
sh.Run "pyw -3.10 """ & root & "\main.py""", 0, False
If Err.Number <> 0 Then
    Err.Clear
    sh.Run """" & root & "\AgriVision.bat""", 1, False
End If
