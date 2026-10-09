"""Database connection and table definitions."""

from pathlib import Path
import streamlit as st

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer,
    String, Text, ForeignKey, CheckConstraint, text
)
from sqlalchemy.engine import URL


# Read credentials from Streamlit Secrets.
settings = st.secrets["mysql"]

url = URL.create(
    "mysql+pymysql",
    username=settings["user"],
    password=settings["password"],
    host=settings["host"],
    port=int(settings["port"]),
    database=settings["database"],
    query={"charset": "utf8mb4"},
)

# Locate ca.pem beside this Python file.
certificate = Path(__file__).resolve().with_name("ca.pem")

engine = create_engine(
    url,
    pool_pre_ping=True,
    connect_args={
        "ssl_ca": str(certificate),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    },
)

metadata = MetaData()
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(80), nullable=False, unique=True),
    Column('name', String(120), nullable=False),
    Column('role', String(12), nullable=False),
    Column('password_hash', String(256), nullable=False),
    Column('active', Integer, nullable=False, server_default='1'),
    Column('failures', Integer, nullable=False, server_default='0'),
    Column('locked_until', Integer, nullable=False, server_default='0'),
    CheckConstraint("role IN ('admin','teacher','parent')"))
teachers = Table('teachers', metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True))
parents = Table('parents', metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('cnic_hash', String(256), nullable=False))
classes = Table('classes', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(80), nullable=False, unique=True))
students = Table('students', metadata,
    Column('id', Integer, primary_key=True),
    Column('student_code', String(40), nullable=False, unique=True),
    Column('name', String(120), nullable=False),
    Column('class_id', Integer, ForeignKey('classes.id'), nullable=False))
student_parents = Table('student_parents', metadata,
    Column('student_id', Integer, ForeignKey('students.id'), primary_key=True),
    Column('parent_id', Integer, ForeignKey('parents.user_id'), primary_key=True))
teacher_classes = Table('teacher_classes', metadata,
    Column('teacher_id', Integer, ForeignKey('teachers.user_id'), primary_key=True),
    Column('class_id', Integer, ForeignKey('classes.id'), primary_key=True))
entries = Table('entries', metadata,
    Column('id', Integer, primary_key=True),
    Column('author_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('class_id', Integer, ForeignKey('classes.id'), nullable=False, index=True),
    Column('student_id', Integer, ForeignKey('students.id'), nullable=True),
    Column('kind', String(20), nullable=False),
    Column('subject', String(80), nullable=False),
    Column('title', String(160), nullable=False),
    Column('body', Text, nullable=False),
    Column('due_date', String(10)),
    Column('created_at', String(25), nullable=False),
    CheckConstraint("kind IN ('Homework','Notice','Activity','Private note')"))
acknowledgements = Table('acknowledgements', metadata,
    Column('entry_id', Integer, ForeignKey('entries.id'), primary_key=True),
    Column('student_id', Integer, ForeignKey('students.id'), primary_key=True),
    Column('parent_id', Integer, ForeignKey('parents.user_id'), primary_key=True),
    Column('seen_at', String(25), nullable=False))
replies = Table('replies', metadata,
    Column('id', Integer, primary_key=True),
    Column('entry_id', Integer, ForeignKey('entries.id'), nullable=False),
    Column('student_id', Integer, ForeignKey('students.id'), nullable=False),
    Column('author_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('body', Text, nullable=False),
    Column('created_at', String(25), nullable=False))

def init_db():
    metadata.create_all(engine)

def query(sql, **params):
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(sql), params).mappings()]

def execute(sql, **params):
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        return result.lastrowid