import os
import sys
import subprocess

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    spec_path = os.path.join(project_dir, "BeatVault.spec")

    print("==================================================")
    print("       Building Standalone BeatVault.exe")
    print("==================================================")
    print(f"Project directory: {project_dir}")
    print(f"Spec file: {spec_path}\n")

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", spec_path]
    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=project_dir)
    if result.returncode == 0:
        exe_path = os.path.join(project_dir, "dist", "BeatVault.exe")
        print("\n==================================================")
        print(" [SUCCESS] Standalone Executable Created!")
        print(f" Path: {exe_path}")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f" File Size: {size_mb:.2f} MB")
        print("==================================================")
    else:
        print(f"\n[ERROR] PyInstaller failed with exit code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
