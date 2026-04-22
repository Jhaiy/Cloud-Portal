import subprocess

# Unused file but might bring it back if it ever benefits me.

subprocess.Popen([
  "powershell",
  "-ExecutionPolicy", "Bypass",
  "-File", "Scripts/Check_Playit.ps1"
])