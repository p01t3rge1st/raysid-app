#!/usr/bin/env python3
"""Build executable locally."""
import subprocess
import sys
import shutil
import platform
from pathlib import Path

def main():
    platform_name = platform.system()
    print(f"Building Raysid App for {platform_name}...")
    
    # Check if running in virtual environment
    if sys.prefix == sys.base_prefix:
        print("ERROR: Not running in a virtual environment!")
        print("Please activate the virtual environment first:")
        print("  source .venv/bin/activate")
        sys.exit(1)
    
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
    # Use the Python executable from the current environment to run PyInstaller
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "raysid-app.spec"],
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
    platform_name = platform.system().lower()
    archive_name = f"dist/raysid-app-{platform_name}-x64"
    shutil.make_archive(archive_name, "zip", "dist", "raysid-app")
    
    # Determine executable name based on platform
    exe_name = "raysid-app.exe" if platform_name == "windows" else "raysid-app"
    
    print("\n✅ Build complete!")
    print(f"\n📦 Output:")
    print(f"   Folder: dist/raysid-app/")
    print(f"   Executable: dist/raysid-app/{exe_name}")
    print(f"   Archive: {archive_name}.zip")
    print(f"\n💡 Test the executable:")
    print(f"   cd dist/raysid-app && ./{exe_name}")

if __name__ == "__main__":
    main()
