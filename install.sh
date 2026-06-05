#!/bin/sh
# ติดตั้ง BOYSER AI: สร้าง venv + ลง deps + ติดตั้ง skills + launcher `boyser-ai`
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

command -v python3 >/dev/null || { echo "ต้องมี python3 ก่อน"; exit 1; }

echo "→ สร้าง virtualenv..."
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --upgrade pip -q
echo "→ ติดตั้ง dependencies..."
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt" -q

echo "→ ติดตั้ง skills (เฉพาะตัวที่ยังไม่มี)..."
mkdir -p "$HOME/.config/boyser-ai/skills"
for s in "$DIR"/skills/*/; do
    name="$(basename "$s")"
    [ -d "$HOME/.config/boyser-ai/skills/$name" ] || cp -r "$s" "$HOME/.config/boyser-ai/skills/$name"
done

echo "→ สร้าง launcher ~/.local/bin/boyser-ai..."
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/boyser-ai" <<EOF
#!/bin/sh
exec "$DIR/.venv/bin/python" "$DIR/agent.py" "\$@"
EOF
chmod +x "$HOME/.local/bin/boyser-ai"

echo ""
echo "✓ เสร็จแล้ว! รันด้วยคำสั่ง: boyser-ai  (ครั้งแรกจะมี wizard ตั้งค่า)"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "  หมายเหตุ: เพิ่ม ~/.local/bin ใน PATH ก่อน (export PATH=\"\$HOME/.local/bin:\$PATH\")" ;;
esac
