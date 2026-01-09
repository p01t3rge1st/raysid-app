#!/usr/bin/env bash
#
# Raysid App - Universal Installer
# Supports: macOS, Debian/Ubuntu, Fedora, Arch Linux, openSUSE
# Fully automatic - no user intervention required
#

# Disable strict mode for better error handling
set +e

REPO_URL="https://github.com/p01t3rge1st/raysid-app.git"
APP_NAME="raysid-app"
DESKTOP_FILE="$HOME/.local/share/applications/raysid-app.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
MIN_PYTHON_VERSION="3.10"

# Colors for output (with fallback for dumb terminals)
if [[ -t 1 ]] && [[ "${TERM:-dumb}" != "dumb" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

print_step() { echo -e "${BLUE}==>${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Cleanup on error
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        print_error "Installation failed with error code $exit_code"
        print_warning "Please report this issue at: https://github.com/p01t3rge1st/raysid-app/issues"
    fi
}
trap cleanup EXIT

# Detect OS
detect_os() {
    case "$OSTYPE" in
        darwin*)  echo "macos" ;;
        linux*)   echo "linux" ;;
        msys*|cygwin*|win32*) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

# Get package manager
get_package_manager() {
    if command -v brew &>/dev/null; then
        echo "brew"
    elif command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v yum &>/dev/null; then
        echo "yum"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v zypper &>/dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

# Find working Python 3.10+
find_python() {
    local candidates=("python3.12" "python3.11" "python3.10" "python3" "python")
    
    for py in "${candidates[@]}"; do
        if command -v "$py" &>/dev/null; then
            local version
            version=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [[ -n "$version" ]]; then
                local major minor
                major=$(echo "$version" | cut -d. -f1)
                minor=$(echo "$version" | cut -d. -f2)
                if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]; then
                    echo "$py"
                    return 0
                fi
            fi
        fi
    done
    
    return 1
}

# Check if running with sudo/root (bad idea for pip)
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "Do not run this script as root/sudo!"
        print_warning "The script will ask for sudo when needed."
        exit 1
    fi
}

# Ensure Homebrew is available on macOS
ensure_homebrew() {
    if command -v brew &>/dev/null; then
        return 0
    fi
    
    print_step "Installing Homebrew (required for macOS)..."
    
    # Non-interactive Homebrew install
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
        print_error "Failed to install Homebrew"
        return 1
    }
    
    # Add Homebrew to PATH for this session
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        # Also add to shell config for future sessions
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile" 2>/dev/null || true
    elif [[ -f "/usr/local/bin/brew" ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    if command -v brew &>/dev/null; then
        print_success "Homebrew installed"
        return 0
    else
        print_error "Homebrew installation failed"
        return 1
    fi
}

# Install Python if not available
install_python() {
    local pkg_manager
    pkg_manager=$(get_package_manager)
    
    print_step "Installing Python 3.11..."
    
    case "$pkg_manager" in
        brew)
            brew install python@3.11 2>/dev/null || brew upgrade python@3.11 2>/dev/null || true
            # Ensure python3.11 is linked
            brew link python@3.11 2>/dev/null || true
            ;;
        apt)
            sudo apt-get update -qq
            sudo apt-get install -y python3 python3-pip python3-venv
            ;;
        dnf|yum)
            sudo $pkg_manager install -y python3 python3-pip
            ;;
        pacman)
            sudo pacman -Sy --noconfirm python python-pip
            ;;
        zypper)
            sudo zypper install -y python3 python3-pip
            ;;
        *)
            print_error "Cannot install Python automatically. Please install Python 3.10+ manually."
            return 1
            ;;
    esac
    
    # Verify installation
    if find_python &>/dev/null; then
        print_success "Python installed successfully"
        return 0
    else
        print_error "Python installation failed"
        return 1
    fi
}

# Install system dependencies
install_system_deps() {
    local os_type pkg_manager
    os_type=$(detect_os)
    pkg_manager=$(get_package_manager)
    
    print_step "Installing system dependencies..."
    
    case "$os_type" in
        macos)
            ensure_homebrew || return 1
            # macOS doesn't need XCB libraries
            print_success "System dependencies ready (macOS)"
            ;;
        linux)
            case "$pkg_manager" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y \
                        python3-pip python3-venv git curl \
                        libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 \
                        libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0 libgl1 \
                        2>/dev/null || true
                    ;;
                dnf|yum)
                    sudo $pkg_manager install -y \
                        python3-pip git curl \
                        libxcb xcb-util xcb-util-image xcb-util-renderutil \
                        xcb-util-keysyms libxkbcommon-x11 mesa-libGL \
                        2>/dev/null || true
                    ;;
                pacman)
                    sudo pacman -Sy --noconfirm \
                        python-pip git curl \
                        libxcb xcb-util xcb-util-image xcb-util-renderutil \
                        xcb-util-keysyms libxkbcommon-x11 mesa \
                        2>/dev/null || true
                    ;;
                zypper)
                    sudo zypper install -y \
                        python3-pip git curl \
                        libxcb1 xcb-util libxcb-image0 libxcb-render-util0 \
                        libxcb-keysyms1 libxkbcommon-x11-0 Mesa-libGL1 \
                        2>/dev/null || true
                    ;;
                *)
                    print_warning "Unknown package manager. Skipping system dependencies."
                    print_warning "If the app fails, install: Python 3.10+, XCB libs, OpenGL"
                    ;;
            esac
            print_success "System dependencies installed"
            ;;
        windows)
            print_warning "Windows detected. Make sure Python 3.10+ is installed from python.org"
            ;;
        *)
            print_warning "Unknown OS. Skipping system dependencies."
            ;;
    esac
}

# Install pipx
install_pipx() {
    local os_type pkg_manager python_cmd
    os_type=$(detect_os)
    pkg_manager=$(get_package_manager)
    python_cmd=$(find_python)
    
    print_step "Installing pipx..."
    
    case "$os_type" in
        macos)
            brew install pipx 2>/dev/null || brew upgrade pipx 2>/dev/null || true
            ;;
        linux)
            case "$pkg_manager" in
                apt)
                    sudo apt-get install -y pipx 2>/dev/null || {
                        # Fallback: install via pip
                        "$python_cmd" -m pip install --user pipx 2>/dev/null || true
                    }
                    ;;
                dnf|yum)
                    sudo $pkg_manager install -y pipx 2>/dev/null || {
                        "$python_cmd" -m pip install --user pipx 2>/dev/null || true
                    }
                    ;;
                pacman)
                    sudo pacman -S --noconfirm python-pipx 2>/dev/null || {
                        "$python_cmd" -m pip install --user pipx 2>/dev/null || true
                    }
                    ;;
                zypper)
                    sudo zypper install -y python3-pipx 2>/dev/null || {
                        "$python_cmd" -m pip install --user pipx 2>/dev/null || true
                    }
                    ;;
                *)
                    "$python_cmd" -m pip install --user pipx 2>/dev/null || true
                    ;;
            esac
            ;;
        *)
            "$python_cmd" -m pip install --user pipx 2>/dev/null || true
            ;;
    esac
    
    # Ensure pipx path is set
    if command -v pipx &>/dev/null; then
        pipx ensurepath 2>/dev/null || true
    elif [[ -f "$HOME/.local/bin/pipx" ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        "$HOME/.local/bin/pipx" ensurepath 2>/dev/null || true
    fi
    
    # Check if pipx is available now
    if command -v pipx &>/dev/null || [[ -f "$HOME/.local/bin/pipx" ]]; then
        print_success "pipx installed"
        return 0
    else
        print_warning "pipx installation may have failed, will try fallback"
        return 1
    fi
}

# Get pipx command (handles PATH issues)
get_pipx_cmd() {
    if command -v pipx &>/dev/null; then
        echo "pipx"
    elif [[ -f "$HOME/.local/bin/pipx" ]]; then
        echo "$HOME/.local/bin/pipx"
    else
        return 1
    fi
}

# Install the Python package
install_app() {
    local python_cmd pipx_cmd
    python_cmd=$(find_python)
    
    print_step "Installing $APP_NAME..."
    
    # Method 1: Try pipx (best)
    if pipx_cmd=$(get_pipx_cmd); then
        print_step "Using pipx for installation..."
        if "$pipx_cmd" install "git+${REPO_URL}" --force 2>/dev/null; then
            print_success "$APP_NAME installed via pipx"
            return 0
        fi
        print_warning "pipx install failed, trying reinstall..."
        "$pipx_cmd" uninstall "$APP_NAME" 2>/dev/null || true
        if "$pipx_cmd" install "git+${REPO_URL}" 2>/dev/null; then
            print_success "$APP_NAME installed via pipx"
            return 0
        fi
    fi
    
    # Method 2: Try installing pipx first
    if ! command -v pipx &>/dev/null && ! [[ -f "$HOME/.local/bin/pipx" ]]; then
        if install_pipx; then
            pipx_cmd=$(get_pipx_cmd)
            if [[ -n "$pipx_cmd" ]] && "$pipx_cmd" install "git+${REPO_URL}" --force 2>/dev/null; then
                print_success "$APP_NAME installed via pipx"
                return 0
            fi
        fi
    fi
    
    # Method 3: Fallback to dedicated venv
    print_warning "pipx not available, creating dedicated virtual environment..."
    
    local VENV_DIR="$HOME/.local/share/raysid-venv"
    local BIN_DIR="$HOME/.local/bin"
    local BIN_LINK="$BIN_DIR/raysid-app"
    
    # Remove old venv if exists
    rm -rf "$VENV_DIR" 2>/dev/null || true
    
    # Create venv
    "$python_cmd" -m venv "$VENV_DIR" || {
        print_error "Failed to create virtual environment"
        print_warning "Try: sudo apt-get install python3-venv  (or equivalent for your distro)"
        return 1
    }
    
    # Upgrade pip and install
    "$VENV_DIR/bin/pip" install --upgrade pip 2>/dev/null || true
    "$VENV_DIR/bin/pip" install "git+${REPO_URL}" || {
        print_error "Failed to install $APP_NAME"
        return 1
    }
    
    # Create bin directory and symlink
    mkdir -p "$BIN_DIR"
    rm -f "$BIN_LINK" 2>/dev/null || true
    ln -sf "$VENV_DIR/bin/raysid-app" "$BIN_LINK"
    
    # Ensure PATH includes ~/.local/bin
    ensure_path_configured
    
    print_success "$APP_NAME installed in dedicated venv"
    return 0
}

# Ensure ~/.local/bin is in PATH
ensure_path_configured() {
    local BIN_DIR="$HOME/.local/bin"
    
    if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
        return 0
    fi
    
    export PATH="$BIN_DIR:$PATH"
    
    # Add to shell configs
    local shell_configs=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile")
    local path_line='export PATH="$HOME/.local/bin:$PATH"'
    
    for config in "${shell_configs[@]}"; do
        if [[ -f "$config" ]]; then
            if ! grep -q '.local/bin' "$config" 2>/dev/null; then
                echo "" >> "$config"
                echo "# Added by raysid-app installer" >> "$config"
                echo "$path_line" >> "$config"
            fi
        fi
    done
    
    print_warning "Added ~/.local/bin to PATH. Restart terminal for permanent effect."
}

# Find the installed raysid-app command
find_raysid_cmd() {
    local pipx_cmd
    
    # Check common locations
    if command -v raysid-app &>/dev/null; then
        command -v raysid-app
        return 0
    elif [[ -f "$HOME/.local/bin/raysid-app" ]]; then
        echo "$HOME/.local/bin/raysid-app"
        return 0
    fi
    
    # Check pipx location
    if pipx_cmd=$(get_pipx_cmd); then
        local pipx_bin
        pipx_bin=$("$pipx_cmd" environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")
        if [[ -f "$pipx_bin/raysid-app" ]]; then
            echo "$pipx_bin/raysid-app"
            return 0
        fi
    fi
    
    return 1
}

# Find icon in installed package
find_package_icon() {
    local pipx_cmd icon_path
    
    # Try pipx environment
    if pipx_cmd=$(get_pipx_cmd); then
        local pipx_venvs
        pipx_venvs=$("$pipx_cmd" environment --value PIPX_LOCAL_VENVS 2>/dev/null || echo "$HOME/.local/share/pipx/venvs")
        
        # Find icon with glob expansion
        for py_ver in 3.12 3.11 3.10; do
            icon_path="$pipx_venvs/raysid-app/lib/python$py_ver/site-packages/raysid/resources/icon.png"
            if [[ -f "$icon_path" ]]; then
                echo "$icon_path"
                return 0
            fi
        done
    fi
    
    # Try dedicated venv
    for py_ver in 3.12 3.11 3.10; do
        icon_path="$HOME/.local/share/raysid-venv/lib/python$py_ver/site-packages/raysid/resources/icon.png"
        if [[ -f "$icon_path" ]]; then
            echo "$icon_path"
            return 0
        fi
    done
    
    # Try local source (if running from repo)
    if [[ -f "src/raysid/resources/icon.png" ]]; then
        echo "src/raysid/resources/icon.png"
        return 0
    fi
    
    return 1
}

# Create desktop entry with icon (Linux only)
create_desktop_entry() {
    local os_type
    os_type=$(detect_os)
    
    # Skip on non-Linux (macOS uses .app bundles)
    if [[ "$os_type" != "linux" ]]; then
        print_step "Skipping desktop entry (not Linux)"
        return 0
    fi
    
    print_step "Creating desktop entry..."
    
    # Find the executable
    local exec_path
    exec_path=$(find_raysid_cmd) || {
        print_warning "Cannot find raysid-app executable for desktop entry"
        return 0
    }
    
    # Create directories
    mkdir -p "$(dirname "$DESKTOP_FILE")" 2>/dev/null || true
    mkdir -p "$ICON_DIR" 2>/dev/null || true
    
    # Get icon
    local icon_src icon_dest
    icon_dest="$ICON_DIR/raysid-app.png"
    
    if icon_src=$(find_package_icon); then
        cp "$icon_src" "$icon_dest" 2>/dev/null && print_success "Icon installed"
    else
        icon_dest="applications-science"
        print_warning "Icon not found, using default"
    fi
    
    # Create .desktop file
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Raysid App
Comment=Desktop application for Raysid gamma spectrometer via BLE
Exec=$exec_path
Icon=$icon_dest
Terminal=false
Categories=Science;Physics;Education;
Keywords=gamma;spectrometer;radiation;ble;bluetooth;
StartupWMClass=raysid-app
EOF

    chmod +x "$DESKTOP_FILE" 2>/dev/null || true
    
    # Update desktop database
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    
    print_success "Desktop entry created"
}

# Main installation flow
main() {
    local os_type python_cmd
    
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}      🔬 Raysid App Installer          ${BLUE}║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
    echo ""
    
    # Safety check
    check_not_root
    
    # Detect OS
    os_type=$(detect_os)
    print_step "Detected OS: $os_type"
    
    if [[ "$os_type" == "windows" ]]; then
        print_error "Windows is not fully supported by this installer."
        print_warning "Please install manually:"
        echo "  1. Install Python 3.10+ from python.org"
        echo "  2. Run: pip install git+$REPO_URL"
        exit 1
    fi
    
    # Install system dependencies first (includes Homebrew on macOS)
    install_system_deps
    
    # Check/install Python
    if python_cmd=$(find_python); then
        local py_version
        py_version=$("$python_cmd" --version 2>/dev/null | cut -d' ' -f2)
        print_success "Python $py_version detected ($python_cmd)"
    else
        print_warning "Python 3.10+ not found, installing..."
        install_python || {
            print_error "Could not install Python. Please install Python 3.10+ manually."
            exit 1
        }
        python_cmd=$(find_python) || {
            print_error "Python still not found after installation."
            exit 1
        }
        print_success "Python installed: $python_cmd"
    fi
    
    # Install the app
    install_app || {
        print_error "Installation failed!"
        exit 1
    }
    
    # Create desktop entry (Linux only)
    create_desktop_entry
    
    # Final message
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Installation complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo ""
    
    local raysid_path
    if raysid_path=$(find_raysid_cmd); then
        echo "  Run from terminal:  raysid-app"
        echo "  Full path: $raysid_path"
    else
        echo "  Run from terminal:  ~/.local/bin/raysid-app"
    fi
    
    if [[ "$os_type" == "linux" ]]; then
        echo "  Or find 'Raysid App' in your application menu"
    fi
    echo ""
    
    # PATH reminder if needed
    if ! command -v raysid-app &>/dev/null; then
        print_warning "You may need to restart your terminal or run:"
        echo "         source ~/.bashrc  # or ~/.zshrc"
        echo ""
    fi
    
    exit 0
}

main "$@"
