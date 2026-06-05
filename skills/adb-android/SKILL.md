---
name: adb-android
description: ควบคุมและตรวจสอบ Android ผ่าน ADB ใช้เมื่อทำงานกับเครื่อง Android, อ่าน UI, automate การแตะ/พิมพ์, หรือ debug แอปบนมือถือ (เช่น BOYSER farm)
---

# Skill: adb-android

1. เช็คก่อน: `adb devices` (ต้องเห็น device + `device` ไม่ใช่ `unauthorized/offline`)
2. คำสั่งพื้นฐาน:
   - shell: `adb shell <cmd>` · ไฟล์: `adb push/pull`
   - แอป: `adb shell pm list packages`, `adb shell am start -n pkg/.Activity`, `am force-stop pkg`
   - log: `adb logcat` (กรอง `| grep`), `adb shell dumpsys <service>`
3. **อ่าน UI** (สำหรับ automate/farm):
   - dump: `adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml`
   - หา element จาก text/resource-id/bounds ใน XML แล้วคำนวณจุดกลางเพื่อแตะ
4. **input**: `adb shell input tap X Y` · `input text 'abc'` · `input swipe x1 y1 x2 y2 ms` · `input keyevent KEYCODE_BACK`
5. root: `adb shell su -c '<cmd>'` (ถ้าเครื่อง root/Magisk)
6. **ระวัง**: คำสั่งที่ลบ/wipe/uninstall/แก้ system prop — ยืนยันกับผู้ใช้ก่อน; ของบน farm อาจมีหลายเครื่อง ระบุ `-s <serial>` ให้ชัด
