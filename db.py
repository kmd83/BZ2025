
import sqlite3
from typing import Optional, Dict, Any
from config import DB_PATH

def _c():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c=_c();cur=c.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,sex TEXT,age INT,height REAL,weight REAL,activity INT,goal TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS weights(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INT,weight REAL,ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.commit();c.close()

def set_profile(uid,sex,age,h,w,act):
    c=_c();cur=c.cursor()
    cur.execute("INSERT INTO users(user_id,sex,age,height,weight,activity) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET sex=?,age=?,height=?,weight=?,activity=?", (uid,sex,age,h,w,act,sex,age,h,w,act))
    c.commit();c.close()

def set_goal(uid,goal):
    c=_c();c.execute("UPDATE users SET goal=? WHERE user_id=?",(goal,uid));c.commit();c.close()

def get_user(uid):
    c=_c();row=c.execute("SELECT * FROM users WHERE user_id=?",(uid,)).fetchone();c.close();return dict(row) if row else None

def add_weight(uid,w):
    c=_c();c.execute("INSERT INTO weights(user_id,weight) VALUES(?,?)",(uid,w));c.commit();c.close()

def recent_weights(uid,limit=7):
    c=_c();rows=c.execute("SELECT ts,weight FROM weights WHERE user_id=? ORDER BY ts DESC LIMIT ?",(uid,limit)).fetchall();c.close();return [(r["ts"],r["weight"]) for r in rows]
