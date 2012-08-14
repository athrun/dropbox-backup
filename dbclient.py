#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Cadet"
__version__ = "$Revision: 1.0 $"

import sqlite3
import datetime
import os
import logging

logging.basicConfig(format='%(levelname)s:%(lineno)d:%(message)s', level=logging.INFO)

class SyncStatusDB (object):

    STATUS_FILE_NAME = "syncstatus.db"

    def __init__ (self, root_dir):
        if not os.path.isdir (root_dir):
            raise IOError ("Directory [%s] does not exist." % root_dir)

        self.db_path = os.path.join (root_dir, SyncStatusDB.STATUS_FILE_NAME)
        self.conn = None

        if not os.path.isfile (self.db_path):
            logging.info ("Initializing DB.")
            self.conn = sqlite3.connect (self.db_path)
            with self.conn:
                self.conn.execute ('''CREATE TABLE status
                                    (date text, cursor text)''')
                self.conn.execute ('''CREATE TABLE entries
                                    (i_path text UNIQUE, path text, rev text)''')
                logging.info ("Created tables in DB.")
        else:
            self.conn = sqlite3.connect (self.db_path)

        self.conn.row_factory = sqlite3.Row

    def reset_db (self):
        with self.conn:
            self.conn.execute ('DELETE from status')
            self.conn.execute ('DELETE from entries')
            logging.info ("Deleted all entries from the DB.")

    def get_cursor (self, position="last"):
        cursor = None
        with self.conn:
            if position == "last":
                for r in self.conn.execute ('SELECT cursor from status order by rowid desc limit 1'):
                    cursor = r[0]
                    break
            else:
                for rows in self.conn.execute ('SELECT * from status'):
                    print rows
        return cursor

    def put_cursor (self, cursor):
        with self.conn:
            data = (datetime.datetime.now(), cursor)
            self.conn.execute ('INSERT INTO status VALUES (?,?)', data)
            logging.info ("Saved cursor [%s] in DB." % cursor)

    def get_file_entries (self):
        entries = []
        with self.conn:
            for row in self.conn.execute ('SELECT * from entries'):
                entry = {}
                for k in row.keys():
                    entry [k] = row [k]
                entries.append (entry)
        return entries

    def get_file_entry (self, i_path):
        entry = {}
        with self.conn:
            data = (i_path,)
            for row in self.conn.execute ('SELECT * from entries WHERE i_path = ?', data):
                for k in row.keys():
                    entry [k] = row [k]
                break
        return entry

    def put_file_entry (self, i_path, metadata):
        # Remove a previous entry if required, before adding the new one
        if self.get_file_entry (i_path):
            self.del_file_entry (i_path)
        # Add new entry
        with self.conn:
            data = (i_path, metadata["path"], metadata.get ("rev", None))
            self.conn.execute ('INSERT INTO entries VALUES (?,?,?)', data)
            logging.info ("Saved entry [%s] in DB." % i_path)

    def del_file_entry (self, i_path):
        with self.conn:
            data = (i_path,)
            self.conn.execute ('DELETE FROM entries WHERE i_path = ?', data)
            logging.info ("Removed entry [%s] from DB." % i_path)


if __name__ == "__main__":
    import sys
    s = SyncStatusDB (sys.argv[1])
    #s.put_cursor ("123qdahr")
    #s.reset_db()
    #print s.get_cursor ()
    #s.del_file_entry ("/bob/pictures.jpg")
    s.put_file_entry ("/bob/pictures.jpg", {"path": "/BoB/PiCtUrEs.JpG", "rev": "OfdsPez123dds"})
    #print s.get_file_entry ("/bob/pictures.jpg")
    print s.get_file_entries ()
