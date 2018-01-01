import os
import sqlite3

class DBCore:
    db_file = "icons.db"
    def __init__(self):
        if os.path.exists(self.db_file):
            return
        with open("schema.sql", 'r') as f:
            schema = f.read()
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.executescript(schema)
            conn.commit()
            cursor.close()
            conn.close()

    def get_url(self, icon_hash):
        """Returns the icon URL based on the icon sha"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tbl_icons WHERE hash=?", (icon_hash,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result is not None:
            return result[1]
        return None

    def set_url(self, icon_hash, url):
        """Sets the URL of an icon hash on the DB"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tbl_icons(hash, URL) values(?,?)", (icon_hash, url,))
        conn.commit()
        cursor.close()
        conn.close()

if __name__ == '__main__':
    db = DBCore()
