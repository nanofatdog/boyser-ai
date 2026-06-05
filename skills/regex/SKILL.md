---
name: regex
description: สร้าง อธิบาย หรือแก้ regular expression ใช้เมื่อผู้ใช้ขอ regex, pattern matching, หรือ find/replace ด้วย pattern
---

# Skill: regex

1. ถามให้ชัด (หรือดูจากตัวอย่าง): อยาก **match อะไร** และ **ไม่ match อะไร** — ขอตัวอย่างจริงทั้งสองแบบ
2. สร้างทีละส่วน อย่ายัดทุกอย่างทีเดียว
3. **อธิบายทุกส่วน**ของ pattern ที่เขียน (anchor, group, quantifier, char class) ให้ผู้ใช้เข้าใจ ไม่ใช่โยน regex ลึกลับให้
4. **ทดสอบจริง** กับตัวอย่าง: รัน `python3 -c "import re; print(re.findall(r'...', '...'))"` หรือ grep ดูว่า match/ไม่ match ตามต้องการ
5. ระบุ flavor: Python `re`, JS, PCRE, grep -E ต่างกันบางจุด (lookbehind, \d ใน POSIX) — เขียนให้ตรงที่ผู้ใช้ใช้
6. เตือน catastrophic backtracking ถ้ามี nested quantifier เช่น `(a+)+`

prefer pattern ที่อ่านออก + ใช้ verbose/comment ถ้าซับซ้อน
