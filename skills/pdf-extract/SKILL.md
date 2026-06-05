---
name: pdf-extract
description: อ่านและดึงข้อมูล/ตาราง/ข้อความจากไฟล์ PDF ใช้เมื่อผู้ใช้ขอแกะ PDF ดึงข้อมูลจาก PDF หรือสรุปเอกสาร PDF
---

# Skill: pdf-extract

1. ดูก่อนว่าเป็น PDF แบบไหน: **text-based** (ก๊อปตัวอักษรได้) หรือ **scanned/image** (เป็นรูป)
2. **Text PDF** (ผ่าน bash + python):
   - ข้อความ: `pdfplumber` หรือ `pypdf` — วนทีละหน้า `page.extract_text()`
   - **ตาราง**: `pdfplumber` `page.extract_tables()` แม่นกว่า แล้วโยนเข้า pandas
3. **Scanned/รูป**: extract_text จะได้ค่าว่าง → ต้อง **OCR** (`pytesseract` + แปลงหน้าเป็นรูปด้วย `pdf2image`) — บอกผู้ใช้ว่าต้องลงเครื่องมือเพิ่มและความแม่นขึ้นกับคุณภาพรูป
4. **ตรวจคุณภาพ**ที่ดึงมาก่อนใช้: ตัวอักษรเพี้ยน/สลับคอลัมน์ไหม (PDF หลายคอลัมน์มักสลับ) — เช็คก่อนสรุป
5. หน้าเยอะ: ทำทีละช่วง; ดึงเสร็จส่งต่อ skill summarize/data-analysis ตามงาน
