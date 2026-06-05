---
name: write-tests
description: เขียนและรันเทสต์ ใช้เมื่อผู้ใช้ขอเขียน test เพิ่ม coverage ทำ TDD หรือทำให้โค้ดมีเทสต์
---

# Skill: write-tests

1. หา framework ที่โปรเจกต์ใช้ก่อน (glob/grep): pytest, unittest, jest, vitest, go test ฯลฯ — ใช้ตัวเดิม อย่าเอาตัวใหม่มาปน
2. ดูโค้ดที่จะเทสต์ เข้าใจ input/output และเคสที่เป็นไปได้
3. เขียนเทสต์ให้ครอบคลุม:
   - happy path (เคสปกติ)
   - edge cases (ว่าง, 0, ลบ, ใหญ่มาก, ตัวอักษรพิเศษ)
   - error cases (input ผิด → ควร raise/return error)
4. **TDD ถ้าแก้บั๊ก**: เขียนเทสต์ที่ reproduce บั๊ก (ให้ fail ก่อน) แล้วค่อยแก้โค้ดให้ผ่าน
5. รันจริงด้วย bash แล้วดูผล แก้จนเขียว
6. กฎ: เทสต์ต้อง isolated (ไม่พึ่งกัน), เร็ว, assert **พฤติกรรม** ไม่ใช่ implementation detail; ตั้งชื่อเทสต์ให้บอกว่าเทสต์อะไร

จบด้วยการรันเทสต์ทั้งชุดให้เห็นว่าผ่านหมด
