#!/usr/bin/env python3
import os
import subprocess
import sys

def run_command(cmd):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print("🚀 Uploading stock trading bot to GitHub...")
    
    # Get the full token
    success, token, error = run_command("gh auth token")
    if not success:
        print(f"❌ Failed to get GitHub token: {error}")
        return False
    
    token = token.strip()
    
    # Set up git remote with token
    remote_url = f"https://{token}@github.com/ab0391/stock-trading-bot.git"
    
    # Remove existing remote and add new one
    run_command("git remote remove origin")
    run_command(f"git remote add origin {remote_url}")
    
    # Push to GitHub
    print("📤 Pushing to GitHub...")
    success, stdout, stderr = run_command("git push -u origin master")
    
    if success:
        print("✅ Successfully uploaded to GitHub!")
        print("🔗 Repository: https://github.com/ab0391/stock-trading-bot")
        return True
    else:
        print(f"❌ Failed to push: {stderr}")
        return False

if __name__ == "__main__":
    main()
