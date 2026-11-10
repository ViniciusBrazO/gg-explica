' Roda scripts\rodar.cmd sem abrir janela preta a cada 15 minutos.
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
args = ""
For Each a In WScript.Arguments
  args = args & " " & a
Next
CreateObject("WScript.Shell").Run "cmd /c """"" & pasta & "\rodar.cmd""" & args & """", 0, True
