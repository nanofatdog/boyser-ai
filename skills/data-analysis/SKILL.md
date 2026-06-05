---
name: data-analysis
description: วิเคราะห์ข้อมูล CSV/ตาราง/ชุดข้อมูล ใช้เมื่อผู้ใช้ขอวิเคราะห์ คำนวณสถิติ หาแนวโน้ม หรือหา insight จากข้อมูล
---

# Skill: data-analysis

1. โหลดด้วย pandas ผ่าน bash: `python3 -c "import pandas as pd; df=pd.read_csv('...'); ..."` (ติดตั้งถ้าจำเป็น)
2. **สำรวจก่อน**: `df.shape`, `df.dtypes`, `df.head()`, `df.isnull().sum()`, `df.describe()` — เข้าใจข้อมูลก่อนสรุป
3. ทำความสะอาดเท่าที่จำเป็น: จัดการ null, type, ค่าซ้ำ, outlier — และ**บอกว่าทำอะไรไป**
4. ตอบคำถามด้วยตัวเลขจริง: groupby/aggregate/correlation ตามที่ถาม
5. กราฟถ้าช่วยให้เห็นภาพ: matplotlib เซฟเป็น .png แล้วบอก path
6. **ระบุ assumption และข้อจำกัด**: sample เล็ก, correlation ≠ causation, ข้อมูลเอนเอียง — อย่าฟันธงเกินข้อมูล

โดยเฉพาะข้อมูลการเงิน/เทรด: ระวัง overfitting, lookahead bias, และอย่าสรุปว่า "กำไรแน่" จาก backtest สั้นๆ
