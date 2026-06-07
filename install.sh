#!/bin/sh
# =============================================================================
# BOYSER AI — Installer for Linux / macOS
# =============================================================================
# Run via:
#   curl -sSL https://raw.githubusercontent.com/nanofatdog/boyser-ai/main/install.sh | sh
#   sh install.sh          (if cloned)
# =============================================================================
set -e

# ---- Colors ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

echo ""
echo "${CYAN}${BOLD}  ✻ BOYSER AI${NC}"
echo "${CYAN}  ───────────────────────────────${NC}"
echo "${CYAN}  CLI coding agent สไตล์ Claude Code${NC}"
echo ""

# ---- Check prerequisites ----
command -v python3 >/dev/null 2>&1 || {
    echo "${RED}✗ Python 3 is required. Install from: https://python.org${NC}"
    exit 1
}

PYVER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "  ✓ Python $PYVER"

# ---- Determine source directory ----
# If running via curl pipe ($0 = sh), clone repo first
SCRIPT_SRC="$0"
if [ "$SCRIPT_SRC" = "sh" ] || [ "$SCRIPT_SRC" = "bash" ] || [ ! -f "$SCRIPT_SRC" ]; then
    # Running from pipe — need to clone
    INSTALL_DIR="${HOME}/.local/share/boyser-ai"
    echo "  → Installing to ${CYAN}${INSTALL_DIR}${NC}"
    echo ""

    if [ -d "$INSTALL_DIR" ]; then
        echo "  → Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull --ff-only 2>/dev/null || {
            echo "  ${YELLOW}⚠ git pull failed, re-cloning...${NC}"
            cd /tmp && rm -rf "$INSTALL_DIR"
            git clone --depth 1 https://github.com/nanofatdog/boyser-ai.git "$INSTALL_DIR"
            cd "$INSTALL_DIR"
        }
    else
        echo "  → Cloning repository..."
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone --depth 1 https://github.com/nanofatdog/boyser-ai.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    DIR="$INSTALL_DIR"
else
    # Running from a script file (local clone)
    DIR="$(cd "$(dirname "$0")" && pwd)"
    echo "  → Installing from ${CYAN}${DIR}${NC}"
fi

# ---- Create virtual environment ----
echo ""
echo "  → Setting up virtual environment..."
python3 -m venv "$DIR/.venv" 2>/dev/null || {
    # Fallback: try python (sometimes python3 doesn't have venv)
    python3 -m pip install virtualenv -q
    python3 -m virtualenv "$DIR/.venv"
}
"$DIR/.venv/bin/pip" install --upgrade pip -q

# ---- Install dependencies ----
echo "  → Installing dependencies..."
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt" -q

# ---- Install skills (only new ones) ----
echo "  → Installing skills..."
SKILL_DIR="${HOME}/.config/boyser-ai/skills"
mkdir -p "$SKILL_DIR"
COUNT=0
for s in "$DIR"/skills/*/; do
    [ -d "$s" ] || continue
    name="$(basename "$s")"
    if [ ! -d "$SKILL_DIR/$name" ]; then
        cp -r "$s" "$SKILL_DIR/$name"
        COUNT=$((COUNT + 1))
    fi
done
echo "     ${COUNT} skills installed (skipped existing)"

# ---- Create launcher ----
echo "  → Creating launcher..."
LAUNCHER_DIR="${HOME}/.local/bin"
mkdir -p "$LAUNCHER_DIR"

LAUNCHER="${LAUNCHER_DIR}/boyser-ai"
cat > "$LAUNCHER" <<LAUNCHER_EOF
#!/bin/sh
exec "$DIR/.venv/bin/python" "$DIR/agent.py" "\$@"
LAUNCHER_EOF
chmod +x "$LAUNCHER"

# ---- Add PATH to shell config (persistence) ----
echo "  → Adding to PATH in shell config..."
_added_path=0
for _rc in "${HOME}/.bashrc" "${HOME}/.zshrc" "${HOME}/.profile" "${HOME}/.bash_profile"; do
    [ -f "$_rc" ] || continue
    if grep -q '\.local/bin' "$_rc" 2>/dev/null; then
        continue  # already in this config
    fi
    echo "" >> "$_rc"
    echo "# Added by BOYSER AI installer" >> "$_rc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$_rc"
    _added_path=1
done
if [ "$_added_path" = "1" ]; then
    echo "     ✓ Added to shell config"
else
    echo "     ✓ Already in PATH"
fi

# Refresh PATH for this session
export PATH="${HOME}/.local/bin:${PATH}"

# ---- Done ----
echo ""
echo "${GREEN}${BOLD}  ✓ BOYSER AI installed successfully!${NC}"
echo ""

# ---- Auto-run ----
_CMD=""
if command -v boyser-ai >/dev/null 2>&1; then
    _CMD="boyser-ai"
elif [ -x "${HOME}/.local/bin/boyser-ai" ]; then
    _CMD="${HOME}/.local/bin/boyser-ai"
fi

if [ -n "$_CMD" ] && [ -t 0 ] && [ -t 1 ]; then
    echo "  ${CYAN}→ Starting BOYSER AI...${NC}"
    echo ""
    exec "$_CMD"
elif [ -n "$_CMD" ]; then
    echo "  Run:  ${CYAN}~/.local/bin/boyser-ai${NC}  (หรือเปิด terminal ใหม่แล้วใช้ ${CYAN}boyser-ai${NC})"
    echo ""
    echo "  ${YELLOW}Tip:${NC} เปิด terminal ใหม่ หรือรันคำสั่งนี้ก่อน:"
    echo "    ${CYAN}source ~/.bashrc && boyser-ai${NC}"
    echo ""
    echo "  หรือสร้าง config ล่วงหน้า:"
    echo "    ${CYAN}~/.local/bin/boyser-ai --setup${NC}"
    echo ""
else
    echo "  Run:  ${CYAN}${HOME}/.local/bin/boyser-ai${NC}"
    echo ""
fi
echo ""
