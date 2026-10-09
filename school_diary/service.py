"""School rules. Every protected operation checks the signed-in user's access."""
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from db import query, execute, engine

KINDS = ('Homework', 'Notice', 'Activity', 'Private note')
KARACHI = ZoneInfo('Asia/Karachi')


def now():
    return datetime.now(KARACHI).isoformat(timespec='seconds')


def today():
    return datetime.now(KARACHI).date()


def digest(value):
    # Same algorithm as the original app: existing passwords still work.
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 600000).hex()
    return f'{salt}${hashed}'


def verify(value, stored):
    try:
        salt, expected = stored.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 600000).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


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


def check_password(password):
    if not 10 <= len(password) <= 256:
        raise ValueError('Use a password between 10 and 256 characters.')
    return password


def actor(uid, roles=('admin', 'teacher', 'parent')):
    rows = query('SELECT id,username,name,role FROM users WHERE id=:id AND active=1', id=uid)
    if not rows or rows[0]['role'] not in roles:
        raise PermissionError('You do not have access to this action.')
    return rows[0]


def login(role, identifier, password, cnic=''):
    """All roles now sign in with username + password. CNIC is registration only."""
    if role not in ('admin', 'teacher', 'parent') or len(password) > 256:
        return None
    candidates = query('SELECT * FROM users WHERE username=:u AND role=:r AND active=1',
                       u=identifier.strip(), r=role)
    if not candidates:
        return None
    user = candidates[0]
    if user['locked_until'] > time.time():
        return None
    if verify(password, user['password_hash']):
        execute('UPDATE users SET failures=0,locked_until=0 WHERE id=:id', id=user['id'])
        return actor(user['id'])
    # Increment inside the database so simultaneous failures are not lost.
    with engine.begin() as conn:
        conn.execute(text('UPDATE users SET failures=failures+1 WHERE id=:id'), {'id': user['id']})
        conn.execute(text('''UPDATE users SET failures=0,locked_until=:until
            WHERE id=:id AND failures>=5'''), {'id': user['id'], 'until': int(time.time())+300})
    return None


def _insert_user(conn, name, username, role, password_hash, cn_hash=None):
    result = conn.execute(text('''INSERT INTO users(name,username,role,password_hash)
        VALUES(:n,:u,:r,:p)'''), dict(n=name, u=username, r=role, p=password_hash))
    uid = result.lastrowid
    if role == 'parent':
        conn.execute(text('INSERT INTO parents(user_id,cnic_hash) VALUES(:u,:h)'), dict(u=uid, h=cn_hash))
    elif role == 'teacher':
        conn.execute(text('INSERT INTO teachers(user_id) VALUES(:u)'), dict(u=uid))
    return uid


def _create_user(name, username, role, password, cnic=''):
    """Bootstrap helper, also used by setup.py's fictional demo."""
    name, username = required(name, 120), required(username, 80)
    if role not in ('admin', 'teacher', 'parent'):
        raise ValueError('Invalid role.')
    ph = digest(check_password(password))
    ch = digest(cnic_digits(cnic)) if role == 'parent' else None
    with engine.begin() as conn:
        return _insert_user(conn, name, username, role, ph, ch)


def create_user(uid, name, username, role, password, cnic=''):
    actor(uid, ('admin',))
    if role not in ('teacher', 'admin'):
        raise ValueError('Create an invitation for a new parent instead.')
    return _create_user(name, username, role, password)


def directory(uid):
    actor(uid, ('admin',))
    return query('SELECT id,username,name,role,active FROM users ORDER BY role,name')


def all_students(uid, include_archived=False):
    actor(uid, ('admin',))
    return query('''SELECT s.*,c.name AS class_name,
        CASE WHEN a.student_id IS NULL THEN 0 ELSE 1 END AS archived
        FROM students s JOIN classes c ON c.id=s.class_id
        LEFT JOIN student_archives a ON a.student_id=s.id'''
        + ('' if include_archived else ' WHERE a.student_id IS NULL') + ' ORDER BY s.name')


def allowed_classes(uid, include_archived=False):
    user = actor(uid, ('admin', 'teacher'))
    sql = '''SELECT c.*,CASE WHEN a.class_id IS NULL THEN 0 ELSE 1 END AS archived
             FROM classes c LEFT JOIN class_archives a ON a.class_id=c.id WHERE 1=1'''
    if user['role'] == 'teacher':
        sql += ' AND EXISTS (SELECT 1 FROM teacher_classes t WHERE t.class_id=c.id AND t.teacher_id=:u)'
    if not include_archived:
        sql += ' AND a.class_id IS NULL'
    return query(sql + ' ORDER BY c.name', u=uid)


def _class_access(uid, class_id, include_archived=True):
    if class_id not in [c['id'] for c in allowed_classes(uid, include_archived)]:
        raise PermissionError('Class is not available to you.')


def class_students(uid, class_id, include_archived=False):
    _class_access(uid, class_id)
    return query('''SELECT s.*,CASE WHEN a.student_id IS NULL THEN 0 ELSE 1 END AS archived
        FROM students s LEFT JOIN student_archives a ON a.student_id=s.id WHERE s.class_id=:c'''
        + ('' if include_archived else ' AND a.student_id IS NULL') + ' ORDER BY s.name', c=class_id)


def children(uid):
    actor(uid, ('parent',))
    return query('''SELECT s.*,c.name AS class_name FROM students s
        JOIN classes c ON c.id=s.class_id JOIN student_parents sp ON sp.student_id=s.id
        WHERE sp.parent_id=:u
        AND NOT EXISTS (SELECT 1 FROM student_archives a WHERE a.student_id=s.id)
        AND NOT EXISTS (SELECT 1 FROM class_archives a WHERE a.class_id=c.id)
        ORDER BY s.name''', u=uid)


def _active_student(student_id):
    rows = query('''SELECT s.* FROM students s WHERE s.id=:s
        AND NOT EXISTS (SELECT 1 FROM student_archives a WHERE a.student_id=s.id)
        AND NOT EXISTS (SELECT 1 FROM class_archives a WHERE a.class_id=s.class_id)''', s=student_id)
    if not rows:
        raise ValueError('Choose an active student.')
    return rows[0]


def add_class(uid, name):
    actor(uid, ('admin',))
    return execute('INSERT INTO classes(name) VALUES(:n)', n=required(name, 80))


def add_student(uid, code, name, class_id):
    actor(uid, ('admin',))
    _class_access(uid, class_id, False)
    return execute('INSERT INTO students(student_code,name,class_id) VALUES(:c,:n,:cl)',
                   c=required(code, 40), n=required(name, 120), cl=class_id)


def _invite_values(uid, guardian_name, cnic):
    code = secrets.token_urlsafe(24)  # 192-bit, single-use secret; never stored as plain text.
    return code, dict(h=hashlib.sha256(code.encode()).hexdigest(),
                     cn=digest(cnic_digits(cnic)), n=required(guardian_name, 120),
                     u=uid, at=now(), expiry=int(time.time())+7*86400)


def _insert_invite(conn, values, student_ids):
    result = conn.execute(text('''INSERT INTO guardian_invitations
        (code_hash,cnic_hash,guardian_name,created_by,created_at,expires_at)
        VALUES(:h,:cn,:n,:u,:at,:expiry)'''), values)
    iid = result.lastrowid
    for sid in student_ids:
        conn.execute(text('INSERT INTO invitation_students(invitation_id,student_id) VALUES(:i,:s)'),
                     dict(i=iid, s=sid))
    return iid


def enroll_student(uid, code, name, class_id, guardian_name='', cnic='', parent_id=None):
    """Student + guardian invitation/link succeed together or roll back together."""
    actor(uid, ('admin',))
    _class_access(uid, class_id, False)
    code, name = required(code, 40), required(name, 120)
    invitation_code, values = (None, None)
    if parent_id is None:
        invitation_code, values = _invite_values(uid, guardian_name, cnic)
    else:
        actor(parent_id, ('parent',))
    with engine.begin() as conn:
        sid = conn.execute(text('INSERT INTO students(student_code,name,class_id) VALUES(:c,:n,:cl)'),
                           dict(c=code, n=name, cl=class_id)).lastrowid
        if parent_id is None:
            _insert_invite(conn, values, [sid])
        else:
            conn.execute(text('INSERT INTO student_parents(student_id,parent_id) VALUES(:s,:p)'), dict(s=sid, p=parent_id))
    return invitation_code


def create_invitation(uid, student_ids, guardian_name, cnic):
    actor(uid, ('admin',))
    ids = sorted(set(student_ids))
    if not ids:
        raise ValueError('Choose at least one student.')
    for sid in ids:
        _active_student(sid)
    code, values = _invite_values(uid, guardian_name, cnic)
    with engine.begin() as conn:
        _insert_invite(conn, values, ids)
    return code


def invitations(uid):
    actor(uid, ('admin',))
    rows = query('''SELECT id,guardian_name,created_at,expires_at,used_by,revoked,failures
                    FROM guardian_invitations ORDER BY id DESC''')
    links = query('''SELECT i.invitation_id,s.student_code FROM invitation_students i
                    JOIN students s ON s.id=i.student_id ORDER BY s.student_code''')
    for r in rows:
        r['students'] = ', '.join(x['student_code'] for x in links if x['invitation_id'] == r['id'])
        r['status'] = ('Used' if r['used_by'] else 'Revoked' if r['revoked'] else
                       'Locked' if r['failures'] >= 5 else 'Expired' if r['expires_at'] <= time.time() else 'Pending')
    return rows


def revoke_invitation(uid, invitation_id):
    actor(uid, ('admin',))
    execute('UPDATE guardian_invitations SET revoked=1 WHERE id=:i AND used_by IS NULL', i=invitation_id)


def register_parent(username, password, cnic, invitation_code):
    username = required(username, 80)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,80}', username):
        raise ValueError('Username: 3–80 letters, numbers, dots, underscores or hyphens.')
    check_password(password)
    if not re.fullmatch(r'[0-9]{13}', cnic.strip()):
        raise ValueError('Enter your 13-digit CNIC without dashes or spaces.')
    code = invitation_code.strip()
    if len(code) > 100:
        raise ValueError('Invitation details are invalid or expired. Contact the school.')
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    rows = query('SELECT * FROM guardian_invitations WHERE code_hash=:h', h=code_hash)
    message = 'Invitation details are invalid, used, locked or expired. Contact the school.'
    if not rows:
        raise ValueError(message)
    invitation = rows[0]
    if (invitation['used_at'] or invitation['revoked'] or invitation['failures'] >= 5
            or invitation['expires_at'] <= time.time()):
        raise ValueError(message)
    if not verify(cnic.strip(), invitation['cnic_hash']):
        execute('UPDATE guardian_invitations SET failures=failures+1 WHERE id=:i', i=invitation['id'])
        raise ValueError(message)
    ph = digest(password)
    # Conditional UPDATE locks/claims the invite; duplicate usernames roll back the claim.
    try:
        with engine.begin() as conn:
            result = conn.execute(text('''UPDATE guardian_invitations SET used_at=:at
                WHERE id=:i AND used_at IS NULL AND revoked=0 AND failures<5 AND expires_at>:t'''),
                dict(at=now(), i=invitation['id'], t=int(time.time())))
            if result.rowcount != 1:
                raise ValueError(message)
            ids = conn.execute(text('''SELECT i.student_id FROM invitation_students i
                JOIN students s ON s.id=i.student_id WHERE i.invitation_id=:i
                AND NOT EXISTS (SELECT 1 FROM student_archives a WHERE a.student_id=s.id)
                AND NOT EXISTS (SELECT 1 FROM class_archives a WHERE a.class_id=s.class_id)'''),
                dict(i=invitation['id'])).scalars().all()
            if not ids:
                raise ValueError('No active children on this invitation. Contact the school.')
            uid = _insert_user(conn, invitation['guardian_name'], username, 'parent', ph, invitation['cnic_hash'])
            for sid in ids:
                conn.execute(text('INSERT INTO student_parents(student_id,parent_id) VALUES(:s,:p)'), dict(s=sid, p=uid))
            conn.execute(text('UPDATE guardian_invitations SET used_by=:u WHERE id=:i'), dict(u=uid, i=invitation['id']))
        return uid
    except IntegrityError as exc:
        raise ValueError('That username is unavailable. Choose another; your invitation is still usable.') from exc


def link_parent(uid, student_id, parent_id):
    actor(uid, ('admin',))
    _active_student(student_id)
    actor(parent_id, ('parent',))
    execute('INSERT INTO student_parents(student_id,parent_id) VALUES(:s,:p)', s=student_id, p=parent_id)


def assign_teacher(uid, teacher_id, class_id):
    actor(uid, ('admin',))
    actor(teacher_id, ('teacher',))
    _class_access(uid, class_id, False)
    execute('INSERT INTO teacher_classes(teacher_id,class_id) VALUES(:t,:c)', t=teacher_id, c=class_id)


def account_links(uid):
    actor(uid, ('admin',))
    return (query('''SELECT s.student_code,u.username AS parent FROM student_parents sp
        JOIN students s ON s.id=sp.student_id JOIN users u ON u.id=sp.parent_id'''),
        query('''SELECT u.username AS teacher,c.name AS class FROM teacher_classes tc
        JOIN users u ON u.id=tc.teacher_id JOIN classes c ON c.id=tc.class_id'''))


def create_entry(uid, class_id, student_id, kind, subject, title, body, due_date=None, student_ids=None):
    _class_access(uid, class_id, False)
    roster = class_students(uid, class_id)
    available = {s['id'] for s in roster}
    selected = (set(student_ids) if student_ids is not None else
                {student_id} if student_id is not None else available)
    if not selected or not selected <= available:
        raise ValueError('Choose one or more active students from this class.')
    if kind not in KINDS:
        raise ValueError('Invalid diary type.')
    if kind == 'Private note' and student_ids is None and student_id is None:
        raise ValueError('Select the students for a private note.')
    if due_date:
        due_date = date.fromisoformat(str(due_date)).isoformat()
    scope = 'selected' if student_id is not None or student_ids is not None else 'class'
    # Legacy app versions see at most the first selected child, never a wider audience.
    fields = dict(a=uid, c=class_id, s=min(selected) if scope=='selected' else None,
                  k=kind, sub=required(subject, 80), t=required(title, 160),
                  b=required(body, 10000), d=due_date, at=now())
    with engine.begin() as conn:
        eid = conn.execute(text('''INSERT INTO entries
            (author_id,class_id,student_id,kind,subject,title,body,due_date,created_at)
            VALUES(:a,:c,:s,:k,:sub,:t,:b,:d,:at)'''), fields).lastrowid
        conn.execute(text('INSERT INTO entry_audiences(entry_id,scope) VALUES(:e,:s)'), dict(e=eid, s=scope))
        for sid in sorted(selected):
            conn.execute(text('INSERT INTO entry_students(entry_id,student_id) VALUES(:e,:s)'), dict(e=eid, s=sid))
    return eid


# New entries have a saved audience. Legacy entries retain their original rules.
AUDIENCE_SQL = '''((EXISTS (SELECT 1 FROM entry_audiences a WHERE a.entry_id=e.id)
    AND EXISTS (SELECT 1 FROM entry_students es WHERE es.entry_id=e.id AND es.student_id=:s))
    OR (NOT EXISTS (SELECT 1 FROM entry_audiences a WHERE a.entry_id=e.id)
    AND (e.student_id IS NULL OR e.student_id=:s)))'''


def diary(uid, student_id=None, class_id=None, on_date=None):
    user = actor(uid)
    on_date = today() if on_date is None else date.fromisoformat(str(on_date))
    sql = '''SELECT e.*,u.name AS teacher_name,a.scope AS audience_scope
        FROM entries e JOIN users u ON u.id=e.author_id
        LEFT JOIN entry_audiences a ON a.entry_id=e.id
        WHERE e.class_id=:c AND SUBSTR(e.created_at,1,10)=:day'''
    if user['role'] == 'parent':
        child = next((s for s in children(uid) if s['id']==student_id), None)
        if child is None:
            raise PermissionError('Student is not linked to your account.')
        class_id = child['class_id']
        sql += ' AND ' + AUDIENCE_SQL
    else:
        _class_access(uid, class_id)
    return query(sql+' ORDER BY e.created_at DESC,e.id DESC', c=class_id, s=student_id, day=on_date.isoformat())


def _entry(uid, entry_id):
    actor(uid, ('admin', 'teacher'))
    rows = query('SELECT * FROM entries WHERE id=:e', e=entry_id)
    if not rows:
        raise PermissionError('Entry unavailable.')
    _class_access(uid, rows[0]['class_id'])
    return rows[0]


def entry_access(uid, entry_id, student_id):
    user = actor(uid)
    rows = query('''SELECT e.* FROM entries e JOIN students s ON s.class_id=e.class_id
        WHERE e.id=:e AND s.id=:s AND ''' + AUDIENCE_SQL, e=entry_id, s=student_id)
    if not rows:
        raise PermissionError('Entry is not available for this student.')
    if user['role']=='parent':
        if student_id not in [s['id'] for s in children(uid)]:
            raise PermissionError('Student is not linked to your account.')
    else:
        _class_access(uid, rows[0]['class_id'])
    return rows[0]


def entry_roster(uid, entry_id):
    e = _entry(uid, entry_id)
    roster = class_students(uid, e['class_id'], True)
    saved = query('SELECT scope FROM entry_audiences WHERE entry_id=:e', e=entry_id)
    if saved:
        ids = {r['student_id'] for r in query('SELECT student_id FROM entry_students WHERE entry_id=:e', e=entry_id)}
        return [s for s in roster if s['id'] in ids]
    return [s for s in roster if e['student_id'] in (None, s['id'])]


def acknowledge(uid, entry_id, student_id):
    actor(uid, ('parent',))
    entry_access(uid, entry_id, student_id)
    try:
        execute('INSERT INTO acknowledgements(entry_id,student_id,parent_id,seen_at) VALUES(:e,:s,:p,:t)',
                e=entry_id, s=student_id, p=uid, t=now())
    except IntegrityError:
        if not query('SELECT 1 FROM acknowledgements WHERE entry_id=:e AND student_id=:s AND parent_id=:p',
                     e=entry_id, s=student_id, p=uid):
            raise


def thread(uid, entry_id, student_id):
    entry_access(uid, entry_id, student_id)
    return query('''SELECT r.id,r.body,r.created_at,u.name,u.role FROM replies r
        JOIN users u ON u.id=r.author_id WHERE r.entry_id=:e AND r.student_id=:s ORDER BY r.id''',
        e=entry_id, s=student_id)


def reply_count(uid, entry_id, student_id=None):
    if student_id is None:
        _entry(uid, entry_id)  # Parent may never request a whole-feed count.
        return query('SELECT COUNT(*) AS n FROM replies WHERE entry_id=:e', e=entry_id)[0]['n']
    entry_access(uid, entry_id, student_id)
    return query('SELECT COUNT(*) AS n FROM replies WHERE entry_id=:e AND student_id=:s', e=entry_id, s=student_id)[0]['n']


def reply(uid, entry_id, student_id, body):
    e = entry_access(uid, entry_id, student_id)
    _active_student(student_id)
    if query('SELECT 1 FROM class_archives WHERE class_id=:c', c=e['class_id']):
        raise ValueError('Archived conversations are read-only.')
    return execute('INSERT INTO replies(entry_id,student_id,author_id,body,created_at) VALUES(:e,:s,:u,:b,:t)',
                   e=entry_id, s=student_id, u=uid, b=required(body, 2000), t=now())


def receipts(uid, entry_id, student_id):
    entry_access(uid, entry_id, student_id)
    return query('''SELECT u.name,a.parent_id,a.seen_at FROM acknowledgements a
        JOIN users u ON u.id=a.parent_id WHERE a.entry_id=:e AND a.student_id=:s ORDER BY a.seen_at''',
        e=entry_id, s=student_id)


def feed_conversations(uid, entry_id):
    """Staff-only aggregation. Never used for a parent's page."""
    _entry(uid, entry_id)
    comments = query('''SELECT r.*,u.name,u.role FROM replies r JOIN users u ON u.id=r.author_id
        WHERE r.entry_id=:e ORDER BY r.id''', e=entry_id)
    seen = query('''SELECT a.*,u.name FROM acknowledgements a JOIN users u ON u.id=a.parent_id
        WHERE a.entry_id=:e ORDER BY a.seen_at''', e=entry_id)
    return [dict(student=s, replies=[r for r in comments if r['student_id']==s['id']],
                 receipts=[r for r in seen if r['student_id']==s['id']]) for s in entry_roster(uid, entry_id)]


def reset_password(uid, target_id, password):
    actor(uid, ('admin',))
    execute('UPDATE users SET password_hash=:p,failures=0,locked_until=0 WHERE id=:u',
            p=digest(check_password(password)), u=target_id)


def change_password(uid, old, new):
    actor(uid)
    row = query('SELECT password_hash FROM users WHERE id=:u', u=uid)[0]
    if len(old)>256 or not verify(old, row['password_hash']):
        raise ValueError('Current password is incorrect.')
    execute('UPDATE users SET password_hash=:p WHERE id=:u', p=digest(check_password(new)), u=uid)


def _protect_admin(uid, target_id):
    if uid == target_id:
        raise ValueError('You cannot remove or disable your own account.')
    rows = query('SELECT role,active FROM users WHERE id=:u', u=target_id)
    if not rows:
        raise ValueError('Account no longer exists.')
    if rows[0]['role']=='admin' and rows[0]['active']:
        if query("SELECT COUNT(*) AS n FROM users WHERE role='admin' AND active=1")[0]['n'] <= 1:
            raise ValueError('Keep at least one enabled administrator.')


def set_active(uid, target_id, active):
    actor(uid, ('admin',))
    if not active:
        _protect_admin(uid, target_id)
    execute('UPDATE users SET active=:a WHERE id=:u', a=int(active), u=target_id)


def removal_plan(uid, kind, target_id):
    actor(uid, ('admin',))
    if kind == 'user':
        _protect_admin(uid, target_id)
        checks = [('entries', 'author_id'), ('replies', 'author_id'),
                  ('acknowledgements', 'parent_id'), ('guardian_invitations', 'created_by'),
                  ('guardian_invitations', 'used_by')]
        history = any(query(f'SELECT 1 FROM {table} WHERE {field}=:i LIMIT 1', i=target_id)
                      for table, field in checks)
        return 'deactivate' if history else 'delete'
    if kind == 'student':
        rows = query('SELECT class_id FROM students WHERE id=:i', i=target_id)
        if not rows:
            raise ValueError('Student no longer exists.')
        history = query('''SELECT 1 FROM entries e WHERE e.student_id=:i
            OR EXISTS (SELECT 1 FROM entry_students es WHERE es.entry_id=e.id AND es.student_id=:i)
            OR (e.class_id=:c AND e.student_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM entry_audiences a WHERE a.entry_id=e.id)) LIMIT 1''',
            i=target_id, c=rows[0]['class_id'])
        return 'archive' if history else 'delete'
    if kind == 'class':
        if not query('SELECT 1 FROM classes WHERE id=:i', i=target_id):
            raise ValueError('Class no longer exists.')
        if query('''SELECT 1 FROM students s WHERE class_id=:i
            AND NOT EXISTS (SELECT 1 FROM student_archives a WHERE a.student_id=s.id) LIMIT 1''', i=target_id):
            raise ValueError('Remove or archive the students in this class first.')
        history = query('SELECT 1 FROM entries WHERE class_id=:i LIMIT 1', i=target_id)
        history = history or query('SELECT 1 FROM students WHERE class_id=:i LIMIT 1', i=target_id)
        return 'archive' if history else 'delete'
    raise ValueError('Unknown record type.')


def remove_record(uid, kind, target_id):
    action = removal_plan(uid, kind, target_id)
    with engine.begin() as conn:
        if kind=='user':
            if action=='deactivate':
                conn.execute(text('UPDATE users SET active=0 WHERE id=:i'), dict(i=target_id))
            else:
                for table, column in [('student_parents','parent_id'), ('teacher_classes','teacher_id'),
                                      ('parents','user_id'), ('teachers','user_id'), ('users','id')]:
                    conn.execute(text(f'DELETE FROM {table} WHERE {column}=:i'), dict(i=target_id))
        elif kind=='student':
            # All outstanding invites mentioning a removed child are revoked in full.
            conn.execute(text('''UPDATE guardian_invitations SET revoked=1 WHERE used_at IS NULL
                AND id IN (SELECT invitation_id FROM invitation_students WHERE student_id=:i)'''), dict(i=target_id))
            if action=='archive':
                if not conn.execute(text('SELECT 1 FROM student_archives WHERE student_id=:i'), dict(i=target_id)).first():
                    conn.execute(text('INSERT INTO student_archives(student_id,archived_at) VALUES(:i,:t)'), dict(i=target_id,t=now()))
            else:
                for table, column in [('invitation_students','student_id'), ('student_parents','student_id'),
                                      ('student_archives','student_id'), ('students','id')]:
                    conn.execute(text(f'DELETE FROM {table} WHERE {column}=:i'), dict(i=target_id))
        elif action=='archive':
            if not conn.execute(text('SELECT 1 FROM class_archives WHERE class_id=:i'), dict(i=target_id)).first():
                conn.execute(text('INSERT INTO class_archives(class_id,archived_at) VALUES(:i,:t)'), dict(i=target_id,t=now()))
        else:
            for table, column in [('teacher_classes','class_id'), ('class_archives','class_id'), ('classes','id')]:
                conn.execute(text(f'DELETE FROM {table} WHERE {column}=:i'), dict(i=target_id))
    return {'delete':'Deleted.', 'archive':'Archived; diary history retained.',
            'deactivate':'Account disabled; diary history retained.'}[action]


def restore_record(uid, kind, target_id):
    actor(uid, ('admin',))
    if kind=='student':
        row = query('SELECT class_id FROM students WHERE id=:i', i=target_id)
        if not row:
            raise ValueError('Student not found.')
        _class_access(uid, row[0]['class_id'], False)
        execute('DELETE FROM student_archives WHERE student_id=:i', i=target_id)
    elif kind=='class':
        execute('DELETE FROM class_archives WHERE class_id=:i', i=target_id)
    else:
        raise ValueError('Unknown archive type.')
