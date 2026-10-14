"""Receipts for scheduled Telegram notifications, retained privately."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class DeliveryLog:
    def __init__(self,data_dir):
        self.path=Path(data_dir)/"deliveries.sqlite3"
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY,channel TEXT,source TEXT,text TEXT,status TEXT,message_id INTEGER,created REAL)")

    def record(self,source,text,status,message_id=None):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("INSERT INTO deliveries(channel,source,text,status,message_id,created) VALUES('telegram',?,?,?,?,?)",
                       (source[:100],text[:4000],status,message_id,time.time()))
            db.execute("DELETE FROM deliveries WHERE id NOT IN (SELECT id FROM deliveries ORDER BY id DESC LIMIT 500)")

    def recent(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT 50")]
