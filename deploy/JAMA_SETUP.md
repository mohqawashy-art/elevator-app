# تجهيز جما للمصاعد — jama.liftcoreapp.com

## المتطلبات
- DNS: `jama` → `A` → `34.18.56.21` ✅
- SSH على السيرفر (GCP Console)

## أمر واحد

```bash
cd ~/liftcore/elevator-app
git pull origin main
bash deploy/provision_jama.sh
```

## بعد التشغيل
1. افتح https://jama.liftcoreapp.com
2. دخول: `admin` / `admin123`
3. **الإعدادات → الشركة**: اسم جما، الشعار، الجوال، السجل
4. **الإعدادات → المستخدمون**: أنشئ حسابك كمدير
5. غيّر كلمة مرور `admin`

## إعادة إنشاء قاعدة فارغة

```bash
sudo systemctl stop liftcore-jama
rm ~/liftcore/jama-elevator-app/instance/jama.db
bash ~/liftcore/elevator-app/deploy/provision_jama.sh
```

## تحديث كود جما (بدون مسح البيانات)

```bash
cd ~/liftcore/jama-elevator-app
git pull origin main
source .venv/bin/activate
pip install -q -r requirements.txt
python scripts/init_install_module.py || true
sudo systemctl restart liftcore-jama
```
