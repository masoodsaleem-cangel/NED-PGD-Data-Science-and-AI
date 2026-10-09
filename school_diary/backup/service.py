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


def _create_user(name, username, role, password, cnic=''):
    name, username = required(name, 120), required(username, 80)
    if len(password) < 10:
        raise ValueError('Use a password of at least 10 characters.')
    if role not in ('admin', 'teacher', 'parent'):
        raise ValueError('Invalid role.')
    cn_hash = digest(cnic_digits(cnic)) if role == 'parent' else None
    with engine.begin() as conn:
        result = conn.execute(text('''INSERT INTO users(name,username,role,password_hash)
            VALUES(:n,:u,:r,:p)'''), dict(n=name,u=username,r=role,p=digest(password)))
        uid = result.lastrowid
        if role == 'parent':
            conn.execute(text('INSERT INTO parents(user_id,cnic_hash) VALUES(:id,:cn)'), dict(id=uid,cn=cn_hash))
        if role == 'teacher':
            conn.execute(text('INSERT INTO teachers(user_id) VALUES(:id)'), dict(id=uid))
        return uid


def create_user(uid, name, username, role, password, cnic=''):
    actor(uid, ('admin',))
    return _create_user(name, username, role, password, cnic)


def add_class(uid, name):
    actor(uid, ('admin',))
    return execute('INSERT INTO classes(name) VALUES(:n)', n=required(name,80))


def add_student(uid, code, name, class_id):
    actor(uid, ('admin',))
    return execute('INSERT INTO students(student_code,name,class_id) VALUES(:c,:n,:cl)',
                   c=required(code,40),n=required(name,120),cl=class_id)


def link_parent(uid, student_id, parent_id):
    actor(uid, ('admin',))
    execute('INSERT INTO student_parents(student_id,parent_id) VALUES(:s,:p)', s=student_id,p=parent_id)


def assign_teacher(uid, teacher_id, class_id):
    actor(uid, ('admin',))
    execute('INSERT INTO teacher_classes(teacher_id,class_id) VALUES(:t,:c)',t=teacher_id,c=class_id)


def allowed_classes(uid):
    user = actor(uid, ('admin','teacher'))
    if user['role'] == 'admin':
        return query('SELECT * FROM classes ORDER BY name')
    return query('''SELECT c.* FROM classes c JOIN teacher_classes tc ON tc.class_id=c.id
                    WHERE tc.teacher_id=:u ORDER BY c.name''',u=uid)


def children(uid):
    actor(uid, ('parent',))
    return query('''SELECT s.*, c.name AS class_name FROM students s
        JOIN classes c ON c.id=s.class_id JOIN student_parents sp ON sp.student_id=s.id
        WHERE sp.parent_id=:u ORDER BY s.name''',u=uid)


def class_students(uid, class_id):
    if class_id not in [c['id'] for c in allowed_classes(uid)]:
        raise PermissionError('Class is not assigned to you.')
    return query('SELECT * FROM students WHERE class_id=:c ORDER BY name',c=class_id)


def create_entry(uid, class_id, student_id, kind, subject, title, body, due_date=None):
    roster = class_students(uid,class_id)
    if student_id is not None and student_id not in [s['id'] for s in roster]:
        raise ValueError('Student does not belong to this class.')
    if kind not in ('Homework','Notice','Activity','Private note'):
        raise ValueError('Invalid diary type.')
    if kind == 'Private note' and student_id is None:
        raise ValueError('Choose a student for a private note.')
    if due_date:
        due_date = date.fromisoformat(str(due_date)).isoformat()
    return execute('''INSERT INTO entries(author_id,class_id,student_id,kind,subject,title,body,due_date,created_at)
        VALUES(:a,:c,:s,:k,:sub,:t,:b,:d,:at)''',a=uid,c=class_id,s=student_id,k=kind,
        sub=required(subject,80),t=required(title,160),b=required(body,10000),d=due_date,at=now())


def diary(uid, student_id=None, class_id=None):
    user = actor(uid)
    base = '''SELECT e.*, u.name AS teacher_name FROM entries e
              JOIN users u ON u.id=e.author_id WHERE e.class_id=:c'''
    if user['role'] == 'parent':
        selected = next((s for s in children(uid) if s['id']==student_id),None)
        if not selected:
            raise PermissionError('Student is not linked to your account.')
        return query(base+' AND (e.student_id IS NULL OR e.student_id=:s) ORDER BY e.created_at DESC, e.id DESC',
                     c=selected['class_id'],s=student_id)
    class_students(uid,class_id)
    return query(base+' ORDER BY e.created_at DESC, e.id DESC',c=class_id)


def entry_access(uid, entry_id, student_id):
    user = actor(uid)
    entry = query('SELECT * FROM entries WHERE id=:e',e=entry_id)
    student = query('SELECT * FROM students WHERE id=:s',s=student_id)
    if not entry or not student:
        raise PermissionError('Entry or student unavailable.')
    e,s = entry[0],student[0]
    if e['class_id'] != s['class_id'] or e['student_id'] not in (None,student_id):
        raise PermissionError('Entry is not available for this student.')
    if user['role']=='parent':
        if student_id not in [c['id'] for c in children(uid)]:
            raise PermissionError('Student is not linked to your account.')
    else:
        class_students(uid,s['class_id'])
    return e


def acknowledge(uid, entry_id, student_id):
    actor(uid,('parent',))
    entry_access(uid,entry_id,student_id)
    if not query('SELECT 1 FROM acknowledgements WHERE entry_id=:e AND student_id=:s AND parent_id=:p',
                 e=entry_id,s=student_id,p=uid):
        execute('INSERT INTO acknowledgements(entry_id,student_id,parent_id,seen_at) VALUES(:e,:s,:p,:t)',
                e=entry_id,s=student_id,p=uid,t=now())


def thread(uid, entry_id, student_id):
    entry_access(uid,entry_id,student_id)
    return query('''SELECT r.body,r.created_at,u.name,u.role FROM replies r
        JOIN users u ON u.id=r.author_id WHERE r.entry_id=:e AND r.student_id=:s ORDER BY r.id''',
        e=entry_id,s=student_id)


def reply(uid, entry_id, student_id, body):
    entry_access(uid,entry_id,student_id)
    execute('INSERT INTO replies(entry_id,student_id,author_id,body,created_at) VALUES(:e,:s,:u,:b,:t)',
            e=entry_id,s=student_id,u=uid,b=required(body,2000),t=now())


def receipts(uid, entry_id, student_id):
    entry_access(uid,entry_id,student_id)
    return query('''SELECT u.name,a.seen_at FROM acknowledgements a JOIN users u ON u.id=a.parent_id
                    WHERE a.entry_id=:e AND a.student_id=:s''',e=entry_id,s=student_id)


def directory(uid):
    actor(uid,('admin',))
    return query('SELECT id,username,name,role,active FROM users ORDER BY role,name')


def reset_password(uid, target_id, password):
    actor(uid,('admin',))
    if len(password)<10:
        raise ValueError('Use at least 10 characters.')
    execute('UPDATE users SET password_hash=:p,failures=0,locked_until=0 WHERE id=:u',p=digest(password),u=target_id)


def change_password(uid, old, new):
    actor(uid)
    row = query('SELECT password_hash FROM users WHERE id=:u',u=uid)[0]
    if not verify(old,row['password_hash']):
        raise ValueError('Current password is incorrect.')
    if len(new)<10:
        raise ValueError('Use at least 10 characters.')
    execute('UPDATE users SET password_hash=:p WHERE id=:u',p=digest(new),u=uid)


def set_active(uid, target_id, active):
    actor(uid,('admin',))
    if uid==target_id:
        raise ValueError('You cannot deactivate your own account.')
    execute('UPDATE users SET active=:a WHERE id=:u',a=int(active),u=target_id)
