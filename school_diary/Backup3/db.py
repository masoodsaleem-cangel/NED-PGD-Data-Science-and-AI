"""Database connection and table definitions."""

import os
from pathlib import Path
from threading import Lock
import streamlit as st

from sqlalchemy import (
    create_engine, event, MetaData, Table, Column, Integer,
    String, Text, ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.engine import URL


def make_engine():
    # Only the automated tests use SQLite; normal runs always use Aiven Secrets.
    test_path = os.getenv('SCHOOL_DIARY_TEST_DB')
    if test_path:
        if not Path(test_path).is_absolute():
            raise ValueError('SCHOOL_DIARY_TEST_DB must be an absolute test database path.')
        result = create_engine(URL.create('sqlite', database=test_path),
                               connect_args={'timeout': 20})
        @event.listens_for(result, 'connect')
        def sqlite_constraints(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        return result
    settings = st.secrets['mysql']
    url = URL.create('mysql+pymysql', username=settings['user'],
                     password=settings['password'], host=settings['host'],
                     port=int(settings['port']), database=settings['database'],
                     query={'charset': 'utf8mb4'})
    certificate = Path(__file__).resolve().with_name('ca.pem')
    return create_engine(url, pool_pre_ping=True, pool_recycle=300,
        connect_args={'ssl_ca': str(certificate), 'ssl_verify_cert': True,
                      'ssl_verify_identity': True})


engine = make_engine()
_schema_lock = Lock()
_schema_ready = False

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

# Additive upgrade: the original ten tables above are unchanged.
student_archives = Table('student_archives', metadata,
    Column('student_id', Integer, ForeignKey('students.id'), primary_key=True),
    Column('archived_at', String(25), nullable=False))
class_archives = Table('class_archives', metadata,
    Column('class_id', Integer, ForeignKey('classes.id'), primary_key=True),
    Column('archived_at', String(25), nullable=False))
guardian_invitations = Table('guardian_invitations', metadata,
    Column('id', Integer, primary_key=True),
    Column('code_hash', String(64), nullable=False, unique=True),
    Column('cnic_hash', String(256), nullable=False),
    Column('guardian_name', String(120), nullable=False),
    Column('created_by', Integer, ForeignKey('users.id'), nullable=False),
    Column('created_at', String(25), nullable=False),
    Column('expires_at', Integer, nullable=False),
    Column('used_by', Integer, ForeignKey('users.id')),
    Column('used_at', String(25)),
    Column('revoked', Integer, nullable=False, server_default='0'),
    Column('failures', Integer, nullable=False, server_default='0'))
invitation_students = Table('invitation_students', metadata,
    Column('invitation_id', Integer, ForeignKey('guardian_invitations.id'), primary_key=True),
    Column('student_id', Integer, ForeignKey('students.id'), primary_key=True))
# A marker distinguishes new snapshot audiences from legacy whole-class entries.
entry_audiences = Table('entry_audiences', metadata,
    Column('entry_id', Integer, ForeignKey('entries.id'), primary_key=True),
    Column('scope', String(12), nullable=False))
entry_students = Table('entry_students', metadata,
    Column('entry_id', Integer, ForeignKey('entries.id'), primary_key=True),
    Column('student_id', Integer, ForeignKey('students.id'), primary_key=True))


# No existing columns are changed. The HMAC key lives only in server Secrets.
invitation_keys = Table('invitation_keys', metadata,
    Column('guardian_key', String(64), primary_key=True),
    Column('invitation_id', Integer, ForeignKey('guardian_invitations.id')),
    Column('attempts', Integer, nullable=False, server_default='0'),
    Column('window_start', Integer, nullable=False, server_default='0'))
invitation_proofs = Table('invitation_proofs', metadata,
    Column('invitation_id', Integer, ForeignKey('guardian_invitations.id'), primary_key=True),
    Column('nonce', String(32), nullable=False), Column('proof', String(64), nullable=False))
registration_gate = Table('registration_gate', metadata,
    Column('id', Integer, primary_key=True),
    Column('attempts', Integer, nullable=False, server_default='0'),
    Column('window_start', Integer, nullable=False, server_default='0'))
activity_log = Table('activity_log', metadata,
    Column('id', Integer, primary_key=True),
    # A snapshot, not an FK: removal must not erase or block historical activity.
    Column('actor_id', Integer), Column('actor_name', String(120), nullable=False),
    Column('action', String(80), nullable=False), Column('created_at', String(25), nullable=False))
UPGRADE_INDEXES = [
    Index('ix_diary_class_date_id', entries.c.class_id, entries.c.created_at, entries.c.id),
    Index('ix_diary_reply_family', replies.c.entry_id, replies.c.student_id, replies.c.id),
    Index('ix_diary_parent_children', student_parents.c.parent_id, student_parents.c.student_id),
    Index('ix_diary_student_invites', invitation_students.c.student_id, invitation_students.c.invitation_id),
    Index('ix_diary_class_roster', students.c.class_id, students.c.name),
    Index('ix_diary_activity_date', activity_log.c.created_at),
]


def init_db():
    """Create missing tables once per process. Never drop, clear, or reseed data."""
    global _schema_ready
    with _schema_lock:
        if not _schema_ready:
            metadata.create_all(engine)
            # create_all skips indexes on pre-existing tables: explicitly upgrade them.
            for index in UPGRADE_INDEXES:
                index.create(engine, checkfirst=True)
            with engine.begin() as conn:
                if not conn.execute(text('SELECT id FROM registration_gate WHERE id=1')).first():
                    conn.execute(text('INSERT INTO registration_gate(id) VALUES(1)'))
            _schema_ready = True


def query(sql, **params):
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(sql), params).mappings()]


def execute(sql, **params):
    with engine.begin() as conn:
        return conn.execute(text(sql), params).lastrowid
