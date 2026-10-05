"""Business rules: all protected actions check the current user's role and scope."""
import hashlib
import hmac
import secrets
import re
import time
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy import text
from db import query, execute, engine


def now():
    return datetime.now(ZoneInfo('Asia/Karachi')).isoformat(timespec='seconds')


def digest(value):
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 600000).hex()
    return f'{salt}${hashed}'


def verify(value, stored):
    salt, expected = stored.split('$')
    actual = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 600000).hex()
    return hmac.compare_digest(actual, expected)


def cnic_digits(value):
    value = value.strip().replace('-', '').replace(' ', '')
    if not re.fullmatch(r'[0-9]{13}', value):
        raise ValueError('CNIC must contain 13 digits.')
    return value


def required(value, maximum):
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f'Please enter text between 1 and {maximum} characters.')
    return value


def actor(uid, roles=('admin', 'teacher', 'parent')):
    rows = query('SELECT id, username, name, role FROM users WHERE id=:id AND active=1', id=uid)
    if not rows or rows[0]['role'] not in roles:
        raise PermissionError('You do not have access to this action.')
    return rows[0]


def login(role, identifier, password, cnic=''):
    if role == 'parent':
        try:
            cnic = cnic_digits(cnic)
        except ValueError:
            return None
        candidates = query('''SELECT u.*, p.cnic_hash FROM users u
            JOIN parents p ON p.user_id=u.id
            JOIN student_parents sp ON sp.parent_id=u.id
            JOIN students s ON s.id=sp.student_id
            WHERE s.student_code=:code AND u.role='parent' AND u.active=1''', code=identifier.strip())
        candidates = [r for r in candidates if verify(cnic, r['cnic_hash'])]
    else:
        candidates = query('SELECT * FROM users WHERE username=:name AND role=:role AND active=1',
                           name=identifier.strip(), role=role)
    for user in candidates:
        if user['locked_until'] > time.time():
            continue
        if verify(password, user['password_hash']):
            execute('UPDATE users SET failures=0, locked_until=0 WHERE id=:id', id=user['id'])
            return actor(user['id'])
        failures = user['failures'] + 1
        execute('UPDATE users SET failures=:f, locked_until=:t WHERE id=:id',
                f=0 if failures >= 5 else failures,
                t=int(time.time()) + 300 if failures >= 5 else 0, id=user['id'])
    return None