# -*- coding: utf-8 -*-
import subprocess
import os

ROOT = r"E:\core-remote-sensing-detect-web"
os.chdir(ROOT)

GIT = ["git", "-c", "user.name=Kong Jie", "-c", "user.email=kongjie_cn@163.com"]


def run(args):
    cmd = GIT + args
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if out.strip():
        print(out)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    return out

run(["reset"])
run(["add", "-A"])
status = run(["status", "-sb"])
if "email_config.json" in status or "sms_config.json" in status:
    print("WARNING: sensitive files in staging!")
run(["commit", "-m", "Initial commit"])
run(["branch", "-M", "main"])
run(["remote", "set-url", "origin", "https://github.com/Pro-Gas-Station/core-remote-sensing-detect-web.git"])
print("--- push ---")
r = subprocess.run(
    GIT + ["push", "-u", "origin", "main"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print(r.stdout or "")
print(r.stderr or "")
if r.returncode != 0:
    print("PUSH_FAILED (auth may be required locally)")
else:
    print("PUSH_OK")
