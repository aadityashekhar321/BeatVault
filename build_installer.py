import os
import sys
import subprocess
import shutil

def find_iscc() -> str:
    """Finds the Inno Setup Command-Line Compiler (ISCC.exe)."""
    # 1. Check if iscc is in PATH
    iscc_path = shutil.which("iscc") or shutil.which("ISCC")
    if iscc_path:
        return iscc_path

    # 2. Check standard installation directories
    candidate_dirs = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 6"),
        os.path.expandvars(r"%ProgramFiles%\Inno Setup 6"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 5"),
        os.path.expandvars(r"%ProgramFiles%\Inno Setup 5"),
        os.path.expandvars(r"%LocalAppData%\Programs\Inno Setup 6"),
        r"C:\Program Files (x86)\Inno Setup 6",
        r"C:\Program Files\Inno Setup 6",
        r"C:\Inno Setup 6",
    ]

    for d in candidate_dirs:
        exe = os.path.join(d, "ISCC.exe")
        if os.path.exists(exe):
            return exe

    return ""

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(project_dir, "dist")
    exe_path = os.path.join(dist_dir, "BeatVault.exe")
    iss_path = os.path.join(project_dir, "installer", "BeatVault.iss")

    print("==================================================")
    print("      BeatVault Windows Setup Installer Builder   ")
    print("==================================================")
    print(f"Project directory: {project_dir}")

    # Step 1: Ensure dist/BeatVault.exe exists
    if not os.path.exists(exe_path):
        print("\n[INFO] dist/BeatVault.exe not found. Building standalone executable first...")
        build_exe_script = os.path.join(project_dir, "build_exe.py")
        res = subprocess.run([sys.executable, build_exe_script], cwd=project_dir)
        if res.returncode != 0:
            print("[ERROR] Failed to build BeatVault.exe with PyInstaller!")
            sys.exit(res.returncode)

    if not os.path.exists(exe_path):
        print("[ERROR] BeatVault.exe still does not exist in dist folder!")
        sys.exit(1)

    print(f"[OK] Source executable found: {exe_path} ({os.path.getsize(exe_path) / (1024*1024):.2f} MB)")

    # Step 2: Locate Inno Setup Compiler
    iscc = find_iscc()
    if not iscc:
        print("\n[ERROR] Inno Setup compiler (ISCC.exe) was not found!")
        print("Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php")
        print("Or run: winget install JRSoftware.InnoSetup")
        sys.exit(1)

    print(f"[OK] Found Inno Setup Compiler: {iscc}")
    print(f"[INFO] Compiling installer script: {iss_path}\n")

    # Step 3: Compile the installer
    cmd = [iscc, iss_path]
    res = subprocess.run(cmd, cwd=os.path.join(project_dir, "installer"))
    if res.returncode == 0:
        installer_path = os.path.join(dist_dir, "BeatVault-Setup.exe")
        print("\n==================================================")
        print(" [SUCCESS] BeatVault-Setup.exe Successfully Created!")
        print("==================================================")
        print(f" Installer: {installer_path}")
        if os.path.exists(installer_path):
            size_mb = os.path.getsize(installer_path) / (1024 * 1024)
            print(f" File Size: {size_mb:.2f} MB")
        print("==================================================")
    else:
        print(f"\n[ERROR] Inno Setup compilation failed with exit code {res.returncode}")
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
