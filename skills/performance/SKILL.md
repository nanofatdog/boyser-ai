---
name: performance
description: หา bottleneck และ optimize ความเร็ว/หน่วยความจำ ใช้เมื่อผู้ใช้บอกว่าช้า กินแรม หรือขอให้ทำให้เร็วขึ้น
---

# Skill: performance

1. **วัดก่อน อย่าเดา**: profile/จับเวลาจริง (`time`, `cProfile`, `console.time`, `EXPLAIN ANALYZE`) หาว่าช้าตรงไหนจริงๆ
2. กฎ 80/20: แก้ **hotspot ตัวจริง** ที่กินเวลาส่วนใหญ่ ไม่ใช่ทุกจุด
3. **Algorithm ก่อน micro-opt**: O(n²)→O(n log n) ชนะการจูนเล็กๆ ทุกอย่าง
4. จุดที่มักช้า: query ใน loop (N+1), งานซ้ำที่ cache ได้, data structure ผิด (list แทน set/dict), IO/network ใน loop ที่ batch ได้, regex/serialize ซ้ำ
5. **อย่า optimize ก่อนเวลา** — ถ้ายังไม่ใช่ปัญหาจริงอย่าทำให้โค้ดอ่านยากเพื่อความเร็วที่ไม่จำเป็น
6. **ยืนยันด้วยตัวเลข before/after** และเช็คว่าผลลัพธ์ยังถูกต้องเหมือนเดิม
