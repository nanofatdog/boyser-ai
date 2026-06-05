---
name: web-scraping
description: ดึงข้อมูลจากเว็บอย่างถูกวิธี ใช้เมื่อผู้ใช้ขอ scrape ดึงข้อมูลจากหน้าเว็บ หรือเก็บข้อมูลอัตโนมัติจากเว็บไซต์
---

# Skill: web-scraping

1. **เช็คก่อน**: มี **API ทางการ** ไหม (ใช้แทน scrape เสมอถ้ามี); ดู robots.txt และ ToS ของเว็บ
2. ดึง HTML: `httpx`/`requests` + parse ด้วย `BeautifulSoup` หรือ `selectolax` (เร็วกว่า) — เจาะ selector/CSS/xpath ที่เฉพาะเจาะจง
3. **หน้า JavaScript ล้วน** (ข้อมูล render ด้วย JS): raw fetch จะไม่เจอข้อมูล → ต้อง headless browser (Playwright/Selenium) หรือหา API ที่หน้าเว็บเรียกเบื้องหลัง (ดู Network tab)
4. **สุภาพ**: ใส่ rate limit (delay ระหว่าง request), ตั้ง User-Agent ที่ระบุตัวตน, ไม่ยิงถี่จนรบกวนเซิร์ฟเวอร์
5. **ทนทาน**: เว็บเปลี่ยน layout บ่อย — เขียนให้ fail ชัดเจน, cache ผลที่ดึงมา, retry แบบมี backoff
6. เคารพข้อมูลส่วนบุคคล/ลิขสิทธิ์ — scrape เฉพาะที่ได้รับอนุญาตและใช้อย่างเหมาะสม
