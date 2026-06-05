---
name: log-analysis
description: ไล่ log หา error/pattern/สาเหตุ ใช้เมื่อผู้ใช้ขอวิเคราะห์ log หาว่าเกิดอะไรขึ้น หรือ debug จากไฟล์ log
---

# Skill: log-analysis

1. ดูรูปแบบ log ก่อน (`head`/`tail`) — timestamp, level, format — และกรอบเวลาที่สนใจ
2. **กรองของสำคัญ**: `grep -iE 'error|warn|exception|fail|traceback'` ; นับความถี่ `| sort | uniq -c | sort -rn`
3. หา **occurrence แรกสุด** ของ error (ต้นเหตุมักอยู่ก่อนอาการที่เห็น) ไม่ใช่อันล่าสุด
4. **correlate**: จับคู่ด้วย timestamp / request-id / trace-id ดูว่าอะไรเกิดก่อน-หลัง นำไปสู่ error
5. หา pattern/spike: error เพิ่มตอนไหน, ตรงกับ deploy/traffic/เวลาหนึ่งๆ ไหม
6. log ใหญ่มาก: ใช้ `grep`/`awk`/`tail -f`/sample ช่วง — อย่าโหลดทั้งไฟล์เข้า context
7. สรุป: อะไรพัง, น่าจะเพราะอะไร (เรียงความเป็นไปได้), ต้องดูอะไรต่อ — ส่งต่อ skill debug ถ้าต้องไล่ในโค้ด
