"""Relational schema and parameterized SQL. SQLite by default; MySQL via DATABASE_URL."""
import os
import configparser
from pathlib import Path
from sqlalchemy import (create_engine, event, MetaData, Table, Column, Integer,
                        String, Text, ForeignKey, CheckConstraint, text)
from sqlalchemy.engine import URL

DEFAULT_DB = 'sqlite:///' + str(Path(__file__).with_name('diary.db'))
config = configparser.ConfigParser(interpolation=None)
config.read(Path(__file__).with_name('config.ini'))
url = os.getenv('DATABASE_URL', DEFAULT_DB)
if not os.getenv('DATABASE_URL') and config.has_section('mysql'):
    section = config['mysql']
    url = URL.create('mysql+pymysql', username=section.get('user', 'root'),
                     password=section.get('password', ''), host=section.get('host', 'localhost'),
                     port=section.getint('port', 3306), database=section.get('database', 'school_diary'),
                     query={'charset': 'utf8mb4'})
engine = create_engine(url, pool_pre_ping=True)
if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
