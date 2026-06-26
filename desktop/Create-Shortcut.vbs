' إنشاء اختصار سطح مكتب — نافذة متصفح واحدة
' الاستخدام: cscript Create-Shortcut.vbs "اسم الشركة" "الرابط" [أيقونة.ico] [1=فتح]
Option Explicit

Dim args, wsh, fso, name, url, iconPath, doLaunch, browser, desktop, sc, scriptDir, rootDir

Set args = WScript.Arguments
If args.Count < 2 Then
  WScript.Echo "Usage: cscript Create-Shortcut.vbs Name Url [Icon] [Launch1]"
  WScript.Quit 1
End If

name = SanitizeName(args(0))
url = NormalizeUrl(args(1))
iconPath = ""
If args.Count >= 3 Then iconPath = Trim(args(2))
doLaunch = True
If args.Count >= 4 Then doLaunch = (Trim(args(3)) = "1")

Set wsh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetParentFolderName(scriptDir)

browser = FindBrowser()
If browser = "" Then
  WScript.Echo "Error: Chrome or Edge not found."
  WScript.Quit 1
End If

iconPath = ResolveIcon(iconPath, wsh, fso, rootDir)
desktop = wsh.SpecialFolders("Desktop")

Set sc = wsh.CreateShortcut(desktop & "\" & name & ".lnk")
sc.TargetPath = browser
sc.Arguments = "--app=" & url & " --start-maximized"
sc.WorkingDirectory = rootDir
sc.WindowStyle = 1
sc.Description = name & " - LiftCore"
If iconPath <> "" Then sc.IconLocation = iconPath & ",0"
sc.Save

WScript.Echo "OK: " & desktop & "\" & name & ".lnk"
WScript.Echo "URL: " & url

If doLaunch Then
  wsh.Run """" & browser & """ --app=" & url & " --start-maximized", 1, False
End If

Function SanitizeName(s)
  Dim bad, i, c
  bad = Array("\", "/", ":", "*", "?", """", "<", ">", "|")
  SanitizeName = Trim(s)
  For i = 0 To UBound(bad)
    SanitizeName = Replace(SanitizeName, bad(i), "")
  Next
  If SanitizeName = "" Then SanitizeName = "LiftCore"
End Function

Function NormalizeUrl(u)
  u = Trim(u)
  If LCase(Left(u, 7)) <> "http://" And LCase(Left(u, 8)) <> "https://" Then
    u = "https://" & u
  End If
  If InStr(LCase(u), "/login") = 0 Then
    If Right(u, 1) <> "/" Then u = u & "/"
    u = u & "login"
  End If
  NormalizeUrl = u
End Function

Function FindBrowser()
  Dim paths, i, p
  paths = Array( _
    wsh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Google\Chrome\Application\chrome.exe", _
    wsh.ExpandEnvironmentStrings("%LocalAppData%") & "\Google\Chrome\Application\chrome.exe", _
    wsh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe", _
    wsh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe" _
  )
  For i = 0 To UBound(paths)
    p = paths(i)
    If fso.FileExists(p) Then FindBrowser = p: Exit Function
  Next
  FindBrowser = ""
End Function

Function ResolveIcon(custom, wsh, fso, rootDir)
  Dim cands, i, p
  If custom <> "" Then
    If fso.FileExists(custom) Then ResolveIcon = custom: Exit Function
  End If
  cands = Array( _
    wsh.ExpandEnvironmentStrings("%USERPROFILE%") & "\Downloads\Liftcore-icon.ico", _
    rootDir & "\static\images\liftcore.ico" _
  )
  For i = 0 To UBound(cands)
    p = cands(i)
    If fso.FileExists(p) Then ResolveIcon = p: Exit Function
  Next
  ResolveIcon = ""
End Function
