---
name: sql
description: เขียนหรือปรับ SQL query ใช้เมื่อผู้ใช้ขอ query ฐานข้อมูล ดึงข้อมูล หรือทำให้ query เร็วขึ้น
---

# Skill: sql

1. ยืนยัน **schema** (ตาราง/คอลัมน์/ความสัมพันธ์) และ **dialect** (PostgreSQL/MySQL/SQLite/...) ก่อน — ถ้ามีไฟล์ migration/schema อ่านก่อน
2. เขียนให้อ่านออก: ขึ้นบรรทัดต่อ clause, ตั้ง alias สื่อความ, ระบุคอลัมน์ที่ต้องการ **ไม่ใช้ `SELECT *`** ใน production
3. JOIN ให้ถูก: เลือก INNER/LEFT ตามความหมาย, ระวัง row บานจาก JOIN ที่ไม่ unique
4. ใช้ **parameterized query** (`?`/`$1`) เสมอเมื่อมี input จากผู้ใช้ — กัน SQL injection ห้ามต่อ string เอง
5. ถ้า query ช้า: `EXPLAIN`/`EXPLAIN ANALYZE` ดู, แนะนำ index บนคอลัมน์ที่ใช้ WHERE/JOIN/ORDER BY, เลี่ยง function บนคอลัมน์ใน WHERE
6. ทดสอบกับข้อมูลจริงถ้าทำได้ (มี db ในเครื่อง) ก่อนบอกว่าเสร็จ

อธิบายสั้นๆ ว่า query ทำอะไรและทำไมเขียนแบบนี้
