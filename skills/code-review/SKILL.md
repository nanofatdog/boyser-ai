---
name: code-review
description: รีวิวโค้ด/diff/PR หาบั๊ก ความถูกต้อง และจุดที่ควรปรับ ใช้เมื่อผู้ใช้ขอรีวิว ตรวจโค้ด ดู PR หรือขอความเห็นที่สอง
---

# Skill: code-review

1. อ่านของจริงก่อน: `git diff` (และ `--staged`) หรือ read_file ไฟล์ที่เกี่ยวข้อง — ดู code path ทั้งเส้น ไม่ใช่แค่บรรทัดที่เปลี่ยน
2. ตรวจตามลำดับความสำคัญ:
   - **Correctness**: logic ผิด, edge case (ค่าว่าง/0/ลบ/ใหญ่มาก), off-by-one, null/None, race condition, ลืม return/await
   - **Error handling**: เคสล้มเหลวจัดการครบไหม, exception เงียบไหม
   - **Security**: input ไม่ validate, secret ในโค้ด, injection (ดู skill security-review ถ้าเน้นด้านนี้)
   - **Reuse/efficiency**: โค้ดซ้ำ, ลูปซ้อนที่ลดได้, query ใน loop
3. แต่ละ finding บอก: `file:line` · severity (สูง/กลาง/ต่ำ) · ทำไมผิด · วิธีแก้สั้นๆ
4. **ยืนยันก่อนรายงาน**: ไล่โค้ดจริงว่าบั๊กเกิดได้จริง อย่าเดา
5. อย่าจับผิดเรื่อง style/naming เว้นแต่ผู้ใช้ขอ — เน้นของที่ทำให้พังหรือผิดจริง

รายงานเรียงจาก severity สูง→ต่ำ ถ้าไม่เจออะไรร้ายแรงก็บอกตรงๆ ว่าโค้ดโอเค
