#!/usr/bin/env bash
set -euo pipefail

# Simple installer for Qt/X11 runtime deps needed by PyQt5's xcb platform plugin.
# Supports apt (Debian/Ubuntu), dnf (Fedora/RHEL), pacman (Arch).

APT_PKGS=(libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0 libgl1)
DNF_PKGS=(libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa-libGL)
PACMAN_PKGS=(libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa)

has_cmd() { command -v "$1" >/dev/null 2>&1; }

if has_cmd apt-get; then
  sudo apt-get update
  sudo apt-get install -y "${APT_PKGS[@]}"
elif has_cmd dnf; then
  sudo dnf install -y "${DNF_PKGS[@]}"
elif has_cmd pacman; then
  sudo pacman -Sy --noconfirm "${PACMAN_PKGS[@]}"
else
  echo "Unsupported package manager. Please install XCB/X11 + OpenGL runtime libs manually." >&2
  exit 1
fi

echo "Qt/X11 dependencies installed. If running headless, start with: xvfb-run -s \"-screen 0 1280x720x24\" .venv/bin/python main.py"