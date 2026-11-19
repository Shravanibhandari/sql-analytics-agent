"""Create sample.db with an `orders` table. Run: python seed_db.py"""
import sqlite3

conn = sqlite3.connect("sample.db")
conn.executescript("""
DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    order_date TEXT,
    customer TEXT,
    amount REAL
);
INSERT INTO orders (order_date, customer, amount) VALUES
 ('2026-03-02','Asha',150),('2026-01-05','Asha',120.5),
 ('2026-02-11','Meera',200),('2026-01-20','Ravi',80),
 ('2026-04-15','Ravi',310),('2026-05-03','Meera',95);
""")
conn.commit()
conn.close()
print("sample.db created with table 'orders'")
