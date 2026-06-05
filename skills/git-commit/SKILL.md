---
name: git-commit
description: เขียน commit message ที่ดีและ commit ให้ถูกหลัก ใช้เมื่อผู้ใช้ขอ commit/บันทึกการเปลี่ยนแปลงด้วย git
---

# Skill: git-commit

ขั้นตอนการ commit ที่ดี:

1. `git status` และ `git diff` (รวม `--staged`) ดูว่าจะ commit อะไรบ้าง อย่า commit ของที่ไม่เกี่ยว
2. ถ้ายังไม่ stage → `git add <ไฟล์ที่ตั้งใจ>` (เลือกเฉพาะที่เกี่ยวกับงานนี้ ไม่ใช้ `git add -A` มั่ว)
3. เขียน message แบบ Conventional Commits:
   - รูปแบบ: `<type>(<scope>): <subject>`
   - type ที่ใช้บ่อย: `feat` `fix` `docs` `refactor` `test` `chore` `style` `perf`
   - subject: ขึ้นต้นด้วยกริยา present-tense สั้นกระชับ ≤ 50 ตัวอักษร ไม่ต้องมี `.` ปิดท้าย
   - ถ้าซับซ้อน เว้นบรรทัดแล้วเขียน body อธิบาย "ทำไม" (ไม่ใช่ "ทำอะไร" ซึ่งดูจาก diff ได้)
4. commit: `git commit -m "..."` (หลาย -m สำหรับ body)
5. ยืนยันด้วย `git log --oneline -1`

กฎ:
- หนึ่ง commit = หนึ่งความเปลี่ยนแปลงเชิงตรรกะ อย่ายัดหลายเรื่องใน commit เดียว
- ห้าม `git push` เว้นแต่ผู้ใช้สั่งชัดเจน
- ถ้ามีไฟล์ลับ (.env, key) โผล่ใน status → เตือนผู้ใช้ก่อน อย่า add
