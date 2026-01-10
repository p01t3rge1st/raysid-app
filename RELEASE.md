# Release Process

## Automated Release (Recommended)

1. **Create a new tag:**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. **GitHub Actions automatically:**
   - Builds Windows executable
   - Creates release on GitHub
   - Uploads `raysid-app-windows-x64.zip`

3. **Download from:** `https://github.com/p01t3rge1st/raysid-app/releases/latest`

## Manual Build (Windows)

Build Windows executable locally:

```bash
# Install build dependencies
pip install -r requirements-build.txt

# Build
python build_windows.py
```

Output: `dist/raysid-app-windows-x64.zip`

## Manual Build (Linux/macOS)

Test installation:

```bash
pip install -e .
raysid-app
```

## Version Bumping

Update version in:
- `pyproject.toml` → `version = "1.0.0"`
- `src/raysid/__init__.py` → `__version__ = "1.0.0"`

## Testing Checklist

Before release:

- [ ] BLE connection works
- [ ] Spectrum plot updates
- [ ] CPS readout works
- [ ] Settings dialog functional
- [ ] Theme switching works
- [ ] Checksum validation logs properly
- [ ] No crashes on disconnect
- [ ] Windows executable runs (if building for Windows)

## Troubleshooting

**PyInstaller fails:**
- Check `requirements-build.txt` has all dependencies
- Try: `pip install --upgrade pyinstaller`
- Clean build: `rm -rf build dist && python build_windows.py`

**Windows EXE won't run:**
- Check Windows Defender / antivirus
- Try running from command prompt to see errors
- Ensure all DLLs are bundled (check `raysid-app.spec`)

**GitHub Actions fails:**
- Check workflow logs
- Verify `requirements-build.txt` is up to date
- Test build locally first
