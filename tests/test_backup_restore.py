"""اختبار نسخ احتياطي واستعادة SQLite (مستقل عن Flask)."""
import os
import shutil
import sqlite3
import tempfile


def test_sqlite_backup_restore_roundtrip():
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, 'liftcore.db')
        conn = sqlite3.connect(db_path)
        conn.execute('CREATE TABLE customers (name TEXT)')
        conn.execute("INSERT INTO customers VALUES ('Backup Test')")
        conn.commit()
        conn.close()

        backup_path = db_path + '.bak'
        shutil.copy2(db_path, backup_path)

        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE customers SET name = 'Modified'")
        conn.commit()
        conn.close()

        shutil.copy2(backup_path, db_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute('SELECT name FROM customers LIMIT 1').fetchone()
        conn.close()
        assert row[0] == 'Backup Test'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
