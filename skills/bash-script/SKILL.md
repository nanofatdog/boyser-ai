---
name: bash-script
description: เขียน bash/shell script ที่ทนทาน ใช้เมื่อผู้ใช้ขอ shell script automation หรือคำสั่งที่ซับซ้อนหลายขั้น
---

# Skill: bash-script

1. ขึ้นต้นด้วย `#!/usr/bin/env bash` และ `set -euo pipefail` (หยุดเมื่อ error, ตัวแปรไม่ตั้งค่า, pipe พัง)
2. **quote ตัวแปรเสมอ** `"$var"` `"${arr[@]}"` — กันพังเรื่อง space/glob
3. เช็ค dependency ที่ต้องใช้ก่อน (`command -v jq >/dev/null || { echo "ต้องมี jq"; exit 1; }`)
4. แยกเป็น function, มี `usage()`/`--help`, รับ argument อย่างชัดเจน
5. จัดการ error และ cleanup (`trap 'rm -f "$tmp"' EXIT` สำหรับไฟล์ชั่วคราว)
6. หลีกเลี่ยงของอันตราย: `rm -rf "$x"/` โดยไม่เช็ค `$x` ว่าง; ถามก่อนทำสิ่งที่ลบ/เขียนทับไม่ย้อนกลับ
7. ทดสอบจริงกับ input ตัวอย่าง; ถ้าเป็นไปได้รัน `shellcheck` ดู

เขียนให้อ่านออก ใส่คอมเมนต์ตรงจุดที่ไม่ชัด
