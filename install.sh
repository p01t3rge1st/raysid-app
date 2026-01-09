#!/usr/bin/env bash
#
# Raysid Gamma Spectrometer - Installer
# Automatically installs system dependencies, the application, and creates a desktop entry
#
set -euo pipefail

REPO_URL="https://github.com/p01t3rge1st/raysid-app.git"
APP_NAME="raysid-app"
DESKTOP_FILE="$HOME/.local/share/applications/raysid-app.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() { echo -e "${BLUE}==>${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Detect package manager and install system dependencies
install_system_deps() {
    print_step "Installing system dependencies..."
    
    if command -v apt-get &>/dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3-pip python3-venv \
            libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 \
            libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0 libgl1
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-pip python3-virtualenv \
            libxcb xcb-util xcb-util-image xcb-util-renderutil \
            xcb-util-keysyms libxkbcommon-x11 mesa-libGL
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python-pip python-virtualenv \
            libxcb xcb-util xcb-util-image xcb-util-renderutil \
            xcb-util-keysyms libxkbcommon-x11 mesa
    else
        print_warning "Unknown package manager. Please install Python 3.10+ and XCB/OpenGL libraries manually."
        return 1
    fi
    
    print_success "System dependencies installed"
}

# Install the Python package
install_app() {
    print_step "Installing $APP_NAME..."
    
    # Ensure ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        print_warning "Adding ~/.local/bin to PATH in your shell config"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc" 2>/dev/null || true
        export PATH="$HOME/.local/bin:$PATH"
    fi
    
    pip install --user "git+${REPO_URL}"
    
    print_success "$APP_NAME installed"
}

# Create desktop entry with icon
create_desktop_entry() {
    print_step "Creating desktop entry..."
    
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    mkdir -p "$ICON_DIR"
    
    # Get icon from installed package
    ICON_PATH="$ICON_DIR/raysid-app.png"
    PACKAGE_ICON=$(python3 -c "import raysid, os; print(os.path.join(os.path.dirname(raysid.__file__), 'resources', 'icon.png'))" 2>/dev/null || echo "")
    
    if [[ -f "$PACKAGE_ICON" ]]; then
        cp "$PACKAGE_ICON" "$ICON_PATH"
        print_success "Icon installed"
    else
        print_warning "Icon not found in package. Using default icon."
        ICON_PATH="applications-science"
    fi
    
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Raysid Gamma Spectrometer
Comment=Desktop application for Raysid gamma spectrometer via BLE
Exec=$HOME/.local/bin/raysid-app
Icon=$ICON_PATH
Terminal=false
Categories=Science;Physics;Education;
Keywords=gamma;spectrometer;radiation;ble;bluetooth;
StartupWMClass=raysid-app
EOF

    chmod +x "$DESKTOP_FILE"
    
    # Update desktop database
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    
    print_success "Desktop entry created"
}

# Main installation flow
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}   🔬 Raysid Gamma Spectrometer Installer   ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Check Python version
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        print_error "Python 3.10+ is required"
        exit 1
    fi
    print_success "Python $(python3 --version | cut -d' ' -f2) detected"
    
    # Install steps
    install_system_deps
    install_app
    create_desktop_entry
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo ""
    echo "  Run from terminal:  raysid-app"
    echo "  Or find 'Raysid Gamma Spectrometer' in your application menu"
    echo ""
    
    # Hint about PATH
    if ! command -v raysid-app &>/dev/null; then
        print_warning "You may need to restart your terminal or run:"
        echo "         export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

main "$@"
