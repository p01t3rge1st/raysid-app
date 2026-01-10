#!/usr/bin/env python3
"""Build Windows executable locally."""
import subprocess
import sys
import shutil
from pathlib import Path

def main():
    print("Building Raysid App for Windows...")
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("ERROR: PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-build.txt"], check=True)
    
    # Clean previous builds
    print("\n[1/3] Cleaning previous builds...")
    for path in ["build", "dist"]:
        if Path(path).exists():
            shutil.rmtree(path)
            print(f"  Removed {path}/")
    
    # Build executable
    print("\n[2/3] Building executable (this may take a few minutes)...")
    result = subprocess.run(
        ["pyinstaller", "--clean", "--noconfirm", "raysid-app.spec"],
        capture_output=False
    )
    
    if result.returncode != 0:
        print("\n❌ Build failed!")
        sys.exit(1)
    
    # Create zip archive
    print("\n[3/3] Creating archive...")
    dist_folder = Path("dist/raysid-app")
    if not dist_folder.exists():
        print("❌ Build output not found!")
        sys.exit(1)
    
    # Create zip
    shutil.make_archive("dist/raysid-app-windows-x64", "zip", "dist", "raysid-app")
    
    print("\n✅ Build complete!")
    print(f"\n📦 Output:")
    print(f"   Folder: dist/raysid-app/")
    print(f"   Executable: dist/raysid-app/raysid-app.exe")
    print(f"   Archive: dist/raysid-app-windows-x64.zip")
    print(f"\n💡 Test the executable:")
    print(f"   cd dist/raysid-app && ./raysid-app.exe")

if __name__ == "__main__":
    main()
