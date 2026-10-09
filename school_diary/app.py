"""Run: python -m streamlit run app.py"""
import time
from datetime import datetime
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import service as svc
from db import init_db

st.set_page_config(page_title='School Diary', page_icon='📖', layout='wide')
st.markdown('''<style>
[data-testid="stMetric"] {padding:16px;border-radius:14px;border:1px solid #8883;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
</style>''', unsafe_allow_html=True)


def run_action(action, message='Saved successfully.', invitation=False):
    """A successful mutation refreshes the page; database details stay out of errors."""
    try:
        result = action()
    except IntegrityError:
        st.error('This record already exists or is still linked to another record. Refresh and try again.')
        return
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
        return
    except SQLAlchemyError:
        st.error('The database could not save this change. Please try again.')
        return
    if invitation and result:
        st.session_state.invitation_code = result
    st.session_state.flash = message
    st.rerun()


def choose(label, rows, key, field='name'):
    labels = {r['id']: r[field] for r in rows}
    return st.selectbox(label, list(labels), format_func=labels.get, key=key)


def student_label(student):
    return f"{student['name']} · {student['student_code']}" + (' (archived)' if student.get('archived') else '')


def select_students(label, rows, key):
    labels = {s['id']: student_label(s) for s in rows}
    return st.multiselect(label, list(labels), format_func=labels.get, key=key)


def login_screen():
    st.title('📖 School Diary')
    st.write('A daily connection between school and home.')
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        signin, register = st.tabs(['Sign in', 'Register as a parent'])
        with signin:
            labels = {'Parent': 'parent', 'Teacher': 'teacher', 'Super admin': 'admin'}
            role_label = st.radio('Sign in as', list(labels), horizontal=True)
            with st.form('login'):
                username = st.text_input('Username', max_chars=80)
                password = st.text_input('Password', type='password', max_chars=256)
                submitted = st.form_submit_button('Sign in', type='primary')
            if submitted:
                user = svc.login(labels[role_label], username, password)
                if user:
                    st.session_state.clear()
                    st.session_state.user_id = user['id']
                    st.session_state.last_activity = time.time()
                    st.rerun()
                st.error('Sign-in failed. Check your username and password, or wait 5 minutes if locked.')
            st.caption('Existing parents: use your account username and password. Ask the school if you do not know your username.')
            st.caption('Forgot your password? Contact the school administrator for a reset.')
        with register:
            st.write('Use the invitation code given to you by your school.')
            with st.form('parent_registration'):
                username = st.text_input('Choose a unique username', max_chars=80,
                                         help='3–80 letters, numbers, dots, underscores or hyphens.')
                password = st.text_input('Choose a password (10+ characters)', type='password', max_chars=256)
                cnic = st.text_input('CNIC — 13 digits, no dashes', type='password', max_chars=13)
                code = st.text_input('Invitation code', type='password', max_chars=100)
                submitted = st.form_submit_button('Create my parent account', type='primary')
            if submitted:
                run_action(lambda: svc.register_parent(username, password, cnic, code),
                           'Account created! Sign in with your new username and password.')
            st.caption('The code works once and expires after 7 days. Your school can issue a replacement.')


def show_invitation_code():
    code = st.session_state.get('invitation_code')
    if code:
        st.success('Invitation created. Copy this code and share it privately with the intended guardian.')
        st.code(code, language=None)
        st.caption('Valid for 7 days and one registration. The school does not need to choose a parent password.')
        st.download_button('Download invitation slip',
            'SCHOOL DIARY — PARENT INVITATION\n\n'
            'Open the school portal and choose Register as a parent.\n'
            'Enter your chosen username, password, CNIC (13 digits) and this code:\n\n'
            +code+'\n\nUse within 7 days. Keep this code private.\n',
            file_name='parent_invitation.txt', mime='text/plain')
        if st.button('I have copied the code — hide it'):
            del st.session_state.invitation_code
            st.rerun()


def remove_control(uid, kind, record_id, label):
    if st.button('×', key=f'remove_{kind}_{record_id}', help=f'Remove {label}'):
        try:
            action = svc.removal_plan(uid, kind, record_id)
            st.session_state.pending_removal = (kind, record_id, label, action)
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))


def confirm_removal(uid):
    pending = st.session_state.get('pending_removal')
    if not pending:
        return
    kind, record_id, label, action = pending
    explanation = {'delete': 'This unused record will be permanently deleted.',
                   'archive': 'This record has diary history. It will be archived and the history kept.',
                   'deactivate': 'This account has history. Sign-in will be disabled and the history kept.'}[action]
    with st.container(border=True):
        st.warning(f'Remove {label}? {explanation}')
        yes, no, _ = st.columns([1, 1, 3])
        if yes.button('Confirm removal', type='primary'):
            def perform():
                result = svc.remove_record(uid, kind, record_id)
                st.session_state.pop('pending_removal', None)
                return result
            run_action(perform, 'Record removed. History was retained where needed.')
        if no.button('Cancel'):
            del st.session_state.pending_removal
            st.rerun()


def admin_panel(uid):
    st.header('School administration')
    users = svc.directory(uid)
    classes = svc.allowed_classes(uid)
    students = svc.all_students(uid)
    parents = [u for u in users if u['role']=='parent' and u['active']]
    teachers = [u for u in users if u['role']=='teacher' and u['active']]
    confirm_removal(uid)
    show_invitation_code()
    overview, people, enrolment, invites, links, access = st.tabs(
        ['Overview', 'Accounts', 'Classes & students', 'Parent invitations', 'Link accounts', 'Account access'])
    with overview:
        cols = st.columns(3)
        cols[0].metric('Active students', len(students))
        cols[1].metric('Active classes', len(classes))
        cols[2].metric('Enabled teachers', len(teachers))
        st.info('New parent: enrol a child → share the invitation code → parent registers with CNIC and chooses a username/password.')
        st.caption('A second guardian gets a separate invitation. Guardians linked to the same child share that child’s conversation.')
    with people:
        st.subheader('Create a staff account')
        with st.form('new_user', clear_on_submit=True):
            role = st.selectbox('Account type', ['teacher', 'admin'])
            name = st.text_input('Full name', max_chars=120)
            username = st.text_input('Unique username', max_chars=80)
            password = st.text_input('Initial password (10+ characters)', type='password', max_chars=256)
            if st.form_submit_button('Create staff account'):
                run_action(lambda: svc.create_user(uid, name, username, role, password))
        st.subheader('User accounts')
        st.caption('× deletes unused accounts or disables accounts with history. You cannot remove your own account.')
        for u in users:
            row, control = st.columns([12, 1])
            row.write(f"{u['name']} · @{u['username']} · {u['role']} · {'Enabled' if u['active'] else 'Disabled'}")
            with control:
                if u['id'] != uid:
                    remove_control(uid, 'user', u['id'], u['username'])
    with enrolment:
        with st.expander('Add a class'):
            with st.form('new_class', clear_on_submit=True):
                class_name = st.text_input('Class and section', placeholder='Grade 3 • A', max_chars=80)
                if st.form_submit_button('Add class'):
                    run_action(lambda: svc.add_class(uid, class_name))
        st.subheader('Enrol a student')
        if classes:
            method = st.radio('Guardian account', ['New parent — create invitation', 'Existing parent — link account'], horizontal=True)
            existing = method.startswith('Existing')
            if existing and not parents:
                st.info('No enabled parent accounts yet. Create an invitation for a new parent.')
            else:
                with st.form('new_student', clear_on_submit=True):
                    code = st.text_input('Student ID', placeholder='ST-2026-001', max_chars=40)
                    name = st.text_input('Student name', max_chars=120)
                    cid = choose('Class', classes, 'student_class')
                    if existing:
                        pid = choose('Parent account', parents, 'enrol_parent', 'username')
                        guardian_name, cnic = '', ''
                    else:
                        guardian_name = st.text_input('Guardian full name', max_chars=120)
                        cnic = st.text_input('Guardian CNIC (13 digits)', type='password', max_chars=13)
                        pid = None
                    if st.form_submit_button('Create student & link guardian' if existing else 'Create student & invitation', type='primary'):
                        run_action(lambda: svc.enroll_student(uid, code, name, cid, guardian_name, cnic, pid),
                                   'Student created.', invitation=not existing)
        else:
            st.info('Add a class first.')
        st.subheader('Students')
        for s in svc.all_students(uid, True):
            row, control = st.columns([12, 1])
            row.write(f"{student_label(s)} · {s['class_name']}")
            with control:
                if s['archived']:
                    if st.button('Restore', key=f"restore_s{s['id']}"):
                        run_action(lambda sid=s['id']: svc.restore_record(uid, 'student', sid))
                else:
                    remove_control(uid, 'student', s['id'], student_label(s))
        st.subheader('Classes')
        for c in svc.allowed_classes(uid, True):
            row, control = st.columns([12, 1])
            row.write(c['name'] + (' (archived)' if c['archived'] else ''))
            with control:
                if c['archived']:
                    if st.button('Restore', key=f"restore_c{c['id']}"):
                        run_action(lambda cid=c['id']: svc.restore_record(uid, 'class', cid))
                else:
                    remove_control(uid, 'class', c['id'], c['name'])
    with invites:
        st.subheader('Invite a guardian for existing children')
        st.caption('Use this for a second guardian, siblings, or a replacement for an expired/locked invitation. Revoke the old invitation first.')
        if students:
            with st.form('new_invitation', clear_on_submit=True):
                selected = select_students('Children to link', students, 'invitation_children')
                name = st.text_input('Guardian name', max_chars=120)
                cnic = st.text_input('CNIC (13 digits)', type='password', max_chars=13)
                if st.form_submit_button('Generate invitation'):
                    run_action(lambda: svc.create_invitation(uid, selected, name, cnic),
                               'Invitation created.', invitation=True)
        for invitation in svc.invitations(uid):
            row, control = st.columns([10, 2])
            expiry = datetime.fromtimestamp(invitation['expires_at'], svc.KARACHI).strftime('%d %b %Y, %H:%M')
            row.write(f"{invitation['guardian_name']} · {invitation['students']} · {invitation['status']}")
            row.caption(f"Invitation #{invitation['id']} · Expires {expiry} (Pakistan time)")
            if invitation['status'] in ('Pending', 'Locked', 'Expired'):
                if control.button('Revoke', key=f"revoke_{invitation['id']}"):
                    run_action(lambda iid=invitation['id']: svc.revoke_invitation(uid, iid), 'Invitation revoked.')
    with links:
        if students and parents:
            with st.form('link_parent'):
                sid = choose('Student', students, 'link_student', 'student_code')
                pid = choose('Existing parent', parents, 'link_parent_id', 'username')
                if st.form_submit_button('Link parent to student'):
                    run_action(lambda: svc.link_parent(uid, sid, pid))
        if teachers and classes:
            with st.form('assign_teacher'):
                tid = choose('Teacher', teachers, 'assign_teacher_id', 'username')
                cid = choose('Assigned class', classes, 'assigned_class')
                if st.form_submit_button('Assign teacher'):
                    run_action(lambda: svc.assign_teacher(uid, tid, cid))
        parent_links, teacher_links = svc.account_links(uid)
        st.subheader('Current links')
        st.dataframe(parent_links, hide_index=True)
        st.dataframe(teacher_links, hide_index=True)
    with access:
        target = choose('Account', users, 'account_target', 'username')
        with st.form('reset_password', clear_on_submit=True):
            new = st.text_input('New password (10+ characters)', type='password', max_chars=256)
            if st.form_submit_button('Reset password'):
                run_action(lambda: svc.reset_password(uid, target, new))
        target_user = next(u for u in users if u['id']==target)
        enabled = st.checkbox('Account enabled', value=bool(target_user['active']), key=f'enabled_{target}')
        if st.button('Save account status'):
            run_action(lambda: svc.set_active(uid, target, enabled))


def compose(uid, cid):
    roster = svc.class_students(uid, cid)
    if not roster:
        st.info('Add active students before publishing.')
        return
    with st.expander('✏️ Write a diary entry'):
        audience = st.radio('Send to', ['Whole class', 'Selected students'], horizontal=True, key=f'audience_{cid}')
        with st.form(f'compose_{cid}', clear_on_submit=True):
            kind = st.selectbox('Type', svc.KINDS)
            selected = select_students('Students', roster, f'compose_students_{cid}') if audience=='Selected students' else None
            subject = st.text_input('Subject', placeholder='Mathematics / General', max_chars=80)
            title = st.text_input('Title', max_chars=160)
            body = st.text_area('Instructions or message', height=130, max_chars=10000)
            has_due = st.checkbox('Include a due date / activity date')
            due = st.date_input('Due / activity date', value=svc.today())
            st.caption('This entry appears under today’s posting date. The due date is separate.')
            if st.form_submit_button('Publish entry', type='primary'):
                run_action(lambda: svc.create_entry(uid, cid, None, kind, subject, title, body,
                                                    due if has_due else None, student_ids=selected), 'Entry published.')


def comments_view(comments):
    for comment in comments:
        with st.chat_message('user' if comment['role']=='parent' else 'assistant'):
            st.caption(f"{comment['name']} · {comment['role']} · {comment['created_at'][:16].replace('T', ' ')}")
            st.text(comment['body'])


def receipts_view(receipts):
    if receipts:
        st.caption('Acknowledged: ' + ' · '.join(
            f"{r['name']} ({r['seen_at'][:16].replace('T', ' ')})" for r in receipts))
    else:
        st.caption('No acknowledgements yet.')


def reply_form(uid, eid, sid):
    with st.form(f'reply_{eid}_{sid}', clear_on_submit=True):
        body = st.text_area('Reply to this family', key=f'reply_body_{eid}_{sid}', max_chars=2000)
        if st.form_submit_button('Send reply'):
            run_action(lambda: svc.reply(uid, eid, sid, body), 'Reply sent.')


def show_entry(uid, entry, sid=None):
    eid = entry['id']
    with st.container(border=True):
        st.caption(f"{entry['kind']} · {entry['subject']} · {entry['teacher_name']}")
        st.subheader(entry['title'])
        st.text(entry['body'])
        st.caption(f"Posted: {entry['created_at'][:16].replace('T', ' ')} (Pakistan time)" +
                   (f" | Due / scheduled: {entry['due_date']}" if entry['due_date'] else ''))
        if sid is not None:
            seen = svc.receipts(uid, eid, sid)
            already_seen = any(r['parent_id']==uid for r in seen)
            if st.button('✓ Acknowledged' if already_seen else '✓ Acknowledge',
                         key=f'ack_{eid}_{sid}', disabled=already_seen):
                run_action(lambda: svc.acknowledge(uid, eid, sid), 'Acknowledgement saved.')
            receipts_view(seen)
            count = svc.reply_count(uid, eid, sid)
            with st.expander(f'💬 Family conversation · {count} replies'):
                st.caption('Shared with your child’s linked guardians and the school.')
                comments_view(svc.thread(uid, eid, sid))
                reply_form(uid, eid, sid)
        else:
            families = svc.feed_conversations(uid, eid)
            count = sum(len(f['replies']) for f in families)
            acknowledged = sum(bool(f['receipts']) for f in families)
            st.caption(f"{len(families)} students · {acknowledged} families acknowledged")
            with st.expander(f'💬 Family conversations · {count} replies'):
                st.caption('Staff view: all family threads. Each family can see only its own child’s thread.')
                for family in families:
                    child = family['student']
                    st.markdown('**'+student_label(child)+'**')
                    receipts_view(family['receipts'])
                    comments_view(family['replies'])
                    if child['archived']:
                        st.caption('Archived student — conversation is read-only.')
                    else:
                        reply_form(uid, eid, child['id'])
                    st.divider()


def diary_panel(uid, role):
    parent = role=='parent'
    sid, cid = None, None
    if parent:
        kids = svc.children(uid)
        if not kids:
            st.info('Ask the school administrator to link an active child to your account.')
            return
        sid = choose('Your child', kids, 'child')
        child = next(s for s in kids if s['id']==sid)
        st.header(f"{child['name']}’s diary")
        st.caption(f"{child['student_code']} · {child['class_name']}")
    else:
        history = st.checkbox('Include archived classes', key='show_archived_classes')
        classes = svc.allowed_classes(uid, history)
        if not classes:
            st.info('No classes available. Please contact the administrator.')
            return
        cid = choose('Class', classes, 'diary_class')
        if not next(c['archived'] for c in classes if c['id']==cid):
            compose(uid, cid)
    st.subheader('Diary feed')
    mode = st.radio('View entries', ['Today', 'Choose a date'], horizontal=True)
    selected_date = svc.today() if mode=='Today' else st.date_input('Posting date', value=svc.today())
    st.caption(f"Entries posted on {selected_date:%d %B %Y} · Pakistan time. Replies and acknowledgements include all dates.")
    entries = svc.diary(uid, student_id=sid, class_id=cid, on_date=selected_date)
    col1, col2 = st.columns([1, 2])
    kind = col1.selectbox('Type filter', ['All']+list(svc.KINDS))
    search = col2.text_input('Search this day’s diary')
    entries = [e for e in entries if (kind=='All' or e['kind']==kind) and
               search.casefold() in (e['title']+' '+e['body']+' '+e['subject']).casefold()]
    if not entries:
        st.info('No matching entries for this date. Choose another date to view earlier posts.')
    for entry in entries:
        show_entry(uid, entry, sid)


def main():
    init_db()
    if st.session_state.get('flash'):
        st.success(st.session_state.pop('flash'))
    if 'user_id' not in st.session_state:
        login_screen()
        return
    if time.time()-st.session_state.get('last_activity', 0)>1800:
        st.session_state.clear()
        st.rerun()
    try:
        user = svc.actor(st.session_state.user_id)
    except PermissionError:
        st.session_state.clear()
        st.rerun()
    st.session_state.last_activity = time.time()
    uid = user['id']
    st.sidebar.title('📖 School Diary')
    st.sidebar.write(user['name'])
    st.sidebar.caption({'admin': 'Super admin', 'teacher': 'Teacher', 'parent': 'Parent'}[user['role']])
    pages = (['Administration'] if user['role']=='admin' else [])+['Diary', 'My password']
    page = st.sidebar.radio('Menu', pages)
    if st.sidebar.button('Sign out'):
        st.session_state.clear()
        st.rerun()
    if page=='Administration':
        admin_panel(uid)
    elif page=='Diary':
        diary_panel(uid, user['role'])
    else:
        st.header('Change password')
        with st.form('my_password', clear_on_submit=True):
            old = st.text_input('Current password', type='password', max_chars=256)
            new = st.text_input('New password (10+ characters)', type='password', max_chars=256)
            if st.form_submit_button('Change password'):
                run_action(lambda: svc.change_password(uid, old, new), 'Password changed.')


try:
    main()
except SQLAlchemyError:
    st.error('The database is temporarily unavailable. Please refresh and try again.')
except (ValueError, PermissionError) as exc:
    st.error(str(exc))
