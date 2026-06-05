---
name: nextjs-prisma
description: patterns สำหรับ Next.js (App Router) + Prisma ใช้เมื่อทำงานกับโปรเจกต์ Next.js หรือ Prisma เช่น webshop
---

# Skill: nextjs-prisma

**Next.js App Router:**
1. Server Component เป็น default — fetch ข้อมูลในนั้นได้ตรงๆ (async); ใส่ `"use client"` เฉพาะที่ต้องใช้ state/event/hook ของ browser
2. Mutation ใช้ **Server Action** หรือ route handler; revalidate (`revalidatePath`/`revalidateTag`) หลังแก้ข้อมูล
3. อย่าส่ง secret/ข้อมูล sensitive ไป client component; env ฝั่ง client ต้องขึ้นต้น `NEXT_PUBLIC_`

**Prisma:**
4. **Client เป็น singleton** — กัน connection ทะลักตอน hot-reload (เก็บใน `globalThis` ใน dev)
5. แก้ schema → `prisma migrate dev --name xxx` (dev) / `migrate deploy` (prod); อย่าแก้ DB มือเปล่า
6. `DATABASE_URL` ใน env เท่านั้น; query ใช้ Prisma (กัน SQL injection อยู่แล้ว) — เลี่ยง raw query เว้นจำเป็น แล้วต้อง parametrize
7. ระวัง N+1: ใช้ `include`/`select` ดึงครั้งเดียว

อ่าน `schema.prisma` และโครงโปรเจกต์ก่อนลงมือเสมอ
