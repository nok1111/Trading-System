#!/usr/bin/env python3
"""
Alvora Trading Platform — Unified Deploy Script
Does 3 things in order:
  1. Build Tauri desktop app → dist-alvora-v1.0.0/
  2. Git commit + push to origin/main
  3. SSH deploy to VPS (git pull + restart services)

Usage:
  python deploy.py              # full deploy (build + commit + vps)
  python deploy.py --build-only # just build Tauri
  python deploy.py --commit-only # just commit + push
  python deploy.py --vps-only   # just deploy to VPS (assumes already pushed)
"""

import subprocess
import sys
import time
import os
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(r"C:\Users\nokturno\Desktop\TRADING PROJECT")
TRADING_CLIENT = PROJECT_ROOT / "trading-client"
DESKTOP_DIR = TRADING_CLIENT / "desktop"
DIST_DIR = TRADING_CLIENT / "dist-alvora-v1.0.0"

VPS_HOST = "76.13.180.80"
VPS_USER = "root"
VPS_PASSWORD = "6yfRBK?t;9+u/eQd"
VPS_REPO_PATH = "/opt/trading-system"

SERVICES = ["auth-server.service", "ai-server.service", "trading-system.service"]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def run(cmd, cwd=None, timeout=300, check=True, shell=True):
    """Run a command and return (exit_code, stdout, stderr)."""
    print(f"\n>>> {cmd}")
    if cwd:
        print(f"    (cwd: {cwd})")
    result = subprocess.run(
        cmd, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if check and result.returncode != 0:
        print(f"[FAILED] exit code: {result.returncode}")
        sys.exit(1)
    print(f"[exit: {result.returncode}]")
    return result.returncode, result.stdout, result.stderr


def ssh_run(ssh, cmd, timeout=60):
    """Run a command on the VPS via SSH."""
    print(f"\n  VPS>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip())
    if err:
        print(f"  STDERR: {err.rstrip()}")
    print(f"  [exit: {exit_code}]")
    return exit_code


# ─── Step 1: Build Tauri ──────────────────────────────────────────────────────

def build_tauri():
    print("\n" + "=" * 60)
    print("STEP 1: Build Tauri Desktop App")
    print("=" * 60)

    # First, typecheck + vite build
    print("\n--- TypeScript check + Vite build ---")
    run("npx tsc --noEmit", cwd=DESKTOP_DIR, timeout=120)
    run("npx vite build", cwd=DESKTOP_DIR, timeout=120)

    # Tauri build (produces .exe + setup.exe)
    print("\n--- Tauri build (this may take several minutes) ---")
    run("npx tauri build", cwd=DESKTOP_DIR, timeout=900)

    # Verify output
    print("\n--- Verifying build output ---")
    alvora_exe = DIST_DIR / "Alvora.exe"
    setup_exe = DIST_DIR / "Alvora_1.0.0_x64-setup.exe"

    if alvora_exe.exists():
        size_mb = alvora_exe.stat().st_size / (1024 * 1024)
        print(f"  Alvora.exe: {size_mb:.1f} MB")
    else:
        print("  [WARNING] Alvora.exe not found!")

    if setup_exe.exists():
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        print(f"  Setup.exe: {size_mb:.1f} MB")
    else:
        print("  [WARNING] Setup.exe not found!")

    print("\n[Tauri build complete]")


# ─── Step 2: Git commit + push ────────────────────────────────────────────────

def git_commit_push():
    print("\n" + "=" * 60)
    print("STEP 2: Git Commit + Push")
    print("=" * 60)

    # Check for changes
    _, status, _ = run("git status --short", cwd=PROJECT_ROOT, check=False)

    if not status.strip():
        print("\n  No changes to commit. Skipping.")
        return

    # Stage all changes
    print("\n--- Staging changes ---")
    run("git add -A", cwd=PROJECT_ROOT)

    # Generate commit message
    commit_msg = """feat: Academy upgrade — 31 tutorials, interactive widgets, gamification, glossary

- 25 new tutorials (31 total) across 9 categories
- 20 interactive widgets replacing code examples (order form, grid bot, RSI/MACD, etc.)
- 6 learning paths with sequential unlock
- 21 gamification badges, XP system (8 levels), streak tracking
- 101-term trading glossary with search
- Quizzes for all 31 tutorials
- Backend: academy_progress model + 4 new endpoints (paths, badges, leaderboard, quiz-result)
- Confetti, level-up modal, badge-earned modal

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"""

    print("\n--- Committing ---")
    run(f'git commit -m "{commit_msg}"', cwd=PROJECT_ROOT, shell=True, check=False)

    # Push
    print("\n--- Pushing to origin/main ---")
    run("git push origin main", cwd=PROJECT_ROOT, timeout=60, check=False)

    # Verify
    print("\n--- Latest commits ---")
    run("git log --oneline -3", cwd=PROJECT_ROOT, check=False)

    print("\n[Git commit + push complete]")


# ─── Step 3: VPS Deploy ───────────────────────────────────────────────────────

def vps_deploy():
    print("\n" + "=" * 60)
    print("STEP 3: VPS Deploy")
    print("=" * 60)

    try:
        import paramiko
    except ImportError:
        print("  [ERROR] paramiko not installed. Run: pip install paramiko")
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"\n  Connecting to {VPS_HOST}...")
    try:
        ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=15)
        print("  Connected.")
    except Exception as e:
        print(f"  [ERROR] SSH connection failed: {e}")
        sys.exit(1)

    # 3a. Check current state
    print("\n--- Checking current VPS state ---")
    ssh_run(ssh, f"cd {VPS_REPO_PATH} && git log --oneline -3")
    ssh_run(ssh, f"cd {VPS_REPO_PATH} && git status --short")

    # 3b. Pull latest
    print("\n--- Pulling latest code ---")
    ssh_run(ssh, f"cd {VPS_REPO_PATH} && git pull origin main", timeout=60)
    ssh_run(ssh, f"cd {VPS_REPO_PATH} && git log --oneline -3")

    # 3c. Install/update dependencies
    print("\n--- Updating dependencies ---")
    ssh_run(ssh, f"cd {VPS_REPO_PATH} && /opt/trading-system/venv/bin/pip install -r requirements.txt --quiet 2>&1 | tail -3", timeout=120)
    ssh_run(ssh, f"cd {VPS_REPO_PATH}/auth-server && /opt/trading-system/auth-server/.venv/bin/pip install -r requirements.txt --quiet 2>&1 | tail -3", timeout=120)
    ssh_run(ssh, f"cd {VPS_REPO_PATH}/ai-server && /opt/trading-system/ai-server/.venv/bin/pip install -r requirements.txt --quiet 2>&1 | tail -3", timeout=120)

    # 3d. Restart services
    for svc in SERVICES:
        print(f"\n--- Restarting {svc} ---")
        ssh_run(ssh, f"systemctl restart {svc}", timeout=15)
        time.sleep(4)
        ssh_run(ssh, f"systemctl is-active {svc}")
        ssh_run(ssh, f"journalctl -u {svc} --no-pager -n 5 --since '30 seconds ago' 2>/dev/null || true")

    # 3e. Final health check
    print("\n--- Health checks ---")
    ssh_run(ssh, 'curl -s -o /dev/null -w "trading-system(8080): %{http_code}\\n" http://localhost:8080/ 2>/dev/null || echo "trading-system: no response"')
    ssh_run(ssh, 'curl -s -o /dev/null -w "auth-server(8000): %{http_code}\\n" http://localhost:8000/health 2>/dev/null || echo "auth-server: no response"')
    ssh_run(ssh, 'curl -s -o /dev/null -w "ai-server(8001): %{http_code}\\n" http://localhost:8001/ 2>/dev/null || echo "ai-server: no response"')

    ssh.close()
    print("\n[VPS deploy complete]")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    build_only = "--build-only" in args
    commit_only = "--commit-only" in args
    vps_only = "--vps-only" in args

    print("=" * 60)
    print("  Alvora Trading Platform — Deploy Script")
    print("=" * 60)

    if build_only:
        build_tauri()
    elif commit_only:
        git_commit_push()
    elif vps_only:
        vps_deploy()
    else:
        # Full deploy: build → commit → vps
        build_tauri()
        git_commit_push()
        vps_deploy()

    print("\n" + "=" * 60)
    print("  Deploy complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
