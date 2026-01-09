#!/usr/bin/env bash
#
# Raysid App - Installer
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

# Detect OS and package manager
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

# Detect package manager and install system dependencies
install_system_deps() {
    print_step "Installing system dependencies..."
    
    OS_TYPE=$(detect_os)
    
    if [[ "$OS_TYPE" == "macos" ]]; then
        # macOS with Homebrew
        if ! command -v brew &>/dev/null; then
            print_step "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            
            # Add brew to PATH for this session
            if [[ -f "/opt/homebrew/bin/brew" ]]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [[ -f "/usr/local/bin/brew" ]]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
        fi
        
        brew install python@3.11 || true
        print_success "System dependencies installed (macOS)"
        
    elif [[ "$OS_TYPE" == "linux" ]]; then
        # Linux package managers
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
        print_success "System dependencies installed (Linux)"
    else
        print_error "Unsupported OS"
        return 1
    fi
}

# Install the Python package
install_app() {
    print_step "Installing $APP_NAME..."
    
    OS_TYPE=$(detect_os)
    
    # Try to use pipx (best practice for PEP 668)
    if command -v pipx &>/dev/null; then
        print_step "Using pipx for installation..."
        pipx install "git+${REPO_URL}" --force
        print_success "$APP_NAME installed via pipx"
        return 0
    fi
    
    # Try to install pipx from system package manager
    print_step "Installing pipx..."
    if [[ "$OS_TYPE" == "macos" ]]; then
        brew install pipx
        pipx ensurepath
        pipx install "git+${REPO_URL}" --force
        print_success "$APP_NAME installed via pipx (macOS)"
        return 0
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y pipx
        pipx install "git+${REPO_URL}" --force
        print_success "$APP_NAME installed via pipx"
        return 0
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y pipx
        pipx install "git+${REPO_URL}" --force
        print_success "$APP_NAME installed via pipx"
        return 0
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python-pipx
        pipx install "git+${REPO_URL}" --force
        print_success "$APP_NAME installed via pipx"
        return 0
    fi
    
    # Fallback: create dedicated venv for the app
    print_warning "pipx not available, creating dedicated virtual environment..."
    VENV_DIR="$HOME/.local/share/raysid-venv"
    BIN_LINK="$HOME/.local/bin/raysid-app"
    
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install "git+${REPO_URL}"
    
    # Create symlink to make it globally available
    mkdir -p "$HOME/.local/bin"
    ln -sf "$VENV_DIR/bin/raysid-app" "$BIN_LINK"
    
    # Ensure PATH includes ~/.local/bin
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        print_warning "Adding ~/.local/bin to PATH in shell config"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc" 2>/dev/null || true
        export PATH="$HOME/.local/bin:$PATH"
    fi
    
    print_success "$APP_NAME installed in dedicated venv"
}

# Create desktop entry with icon
create_desktop_entry() {
    print_step "Creating desktop entry..."
    
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    mkdir -p "$ICON_DIR"
    
    # Get icon from installed package
    ICON_PATH="$ICON_DIR/raysid-app.png"
    
    # Try to find icon in pipx environment first
    if command -v pipx &>/dev/null && pipx list | grep -q raysid-app; then
        PACKAGE_ICON=$(pipx runpip raysid-app show -f raysid-app | grep 'resources/icon.png' | awk '{print $1}')
        if [[ -n "$PACKAGE_ICON" ]]; then
            PIPX_VENV=$(pipx environment --value PIPX_LOCAL_VENVS)/raysid-app
            FULL_ICON_PATH="$PIPX_VENV/lib/python*/site-packages/raysid/resources/icon.png"
            FULL_ICON_PATH=$(echo $FULL_ICON_PATH)  # Expand glob
            if [[ -f "$FULL_ICON_PATH" ]]; then
                cp "$FULL_ICON_PATH" "$ICON_PATH"
                print_success "Icon installed from pipx package"
            fi
        fi
    # Try venv installation
    elif [[ -f "$HOME/.local/share/raysid-venv/lib/python3*/site-packages/raysid/resources/icon.png" ]]; then
        VENV_ICON=$(echo "$HOME/.local/share/raysid-venv/lib/python3*/site-packages/raysid/resources/icon.png")
        cp "$VENV_ICON" "$ICON_PATH"
        print_success "Icon installed from venv"
    # Try local source if running from repo
    elif [[ -f "src/raysid/resources/icon.png" ]]; then
        cp "src/raysid/resources/icon.png" "$ICON_PATH"
        print_success "Icon installed from local source"
    else
        print_warning "Icon not found in package. Using default icon."
        ICON_PATH="applications-science"
    fi
    
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Raysid App
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
    echo -e "${BLUE}║${NC}   🔬 Raysid App Installer   ${BLUE}║${NC}"
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
    echo "  Or find 'Raysid App' in your application menu"
    echo ""
    
    # Hint about PATH
    if ! command -v raysid-app &>/dev/null; then
        print_warning "You may need to restart your terminal or run:"
        echo "         export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

main "$@"
