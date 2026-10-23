Option Explicit
Dim fso, shell, root, python, pythonw, marker, scriptPath, batch, checkCmd, checkResult
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
python = root & "\.venv311\Scripts\python.exe"
pythonw = root & "\.venv311\Scripts\pythonw.exe"
marker = root & "\.venv311\deps-installed.ok"
scriptPath = root & "\scripts\safe_main.py"
batch = root & "\Launch_Spiker.bat"

If fso.FileExists(marker) And fso.FileExists(python) And fso.FileExists(pythonw) And fso.FileExists(scriptPath) Then
    ' Minimal metadata validation is fast and catches a stale installation marker.
    checkCmd = Chr(34) & python & Chr(34) & " -c " & Chr(34) & _
        "import importlib.metadata as m; [m.version(x) for x in ['PySide6','vosk','pywhispercpp','PyAudio','imageio-ffmpeg','keyring','python-docx']]" & Chr(34)
    checkResult = shell.Run(checkCmd, 0, True)
    If checkResult = 0 Then
        shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, False
    ElseIf fso.FileExists(batch) Then
        shell.Run Chr(34) & batch & Chr(34), 1, False
    Else
        MsgBox "Launch_Spiker.bat was not found.", vbCritical, "Spiker"
    End If
ElseIf fso.FileExists(batch) Then
    ' First installation/repair remains visible instead of hiding downloads and errors.
    shell.Run Chr(34) & batch & Chr(34), 1, False
Else
    MsgBox "Launch_Spiker.bat was not found.", vbCritical, "Spiker"
End If
