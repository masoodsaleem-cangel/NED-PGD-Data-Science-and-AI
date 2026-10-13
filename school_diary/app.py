"""Run: python -m streamlit run app.py"""
import time
import hashlib
import html
from datetime import datetime, date
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import service as svc
from db import init_db
from portal_message import render_welcome, message_editor
from diary_calendar import stretch

st.set_page_config(page_title='School Diary', page_icon='📖', layout='wide')
st.html('''<style>
[data-testid="stMetric"] {padding:16px;border-radius:14px;border:1px solid #8883;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
/* Keep dialogs inside small screens; long messages scroll inside the dialog. */
[role="dialog"] {max-width:calc(100vw - 24px) !important;max-height:90dvh;overflow-y:auto;}
/* Limit strong borders to feed cards and reply cards. */
[class*="st-key-feed_card_"] {border:3px solid #68408A !important;border-radius:14px;padding:16px;}
[class*="st-key-reply_card_"] {border:3px solid #68408A !important;border-radius:12px;padding:8px;}
[class*="st-key-reply_indicator_"] button {border:0;background:transparent;padding:0;min-height:28px;}
[class*="st-key-reply_indicator_"] button p {font-size:0.8rem;}
[class*="st-key-reply_indicator_new_"] button,
[class*="st-key-reply_indicator_new_"] button p,
[class*="st-key-reply_indicator_new_"] button span {color:#16803c !important;}
.st-key-feed_toolbar [data-testid="stHorizontalBlock"] {flex-wrap:nowrap;gap:8px;}
.st-key-feed_toolbar [data-testid="stColumn"] {min-width:0 !important;}
.st-key-feed_toolbar {max-width:170px;}
</style>''')


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
    st.session_state.pop('month_counts',None)
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
                code = st.text_input('Invitation code', type='password', max_chars=100, help='Enter the six digits exactly, including any leading zero. Older long vouchers are also accepted until expiry.')
                submitted = st.form_submit_button('Create my parent account', type='primary')
            if submitted:
                run_action(lambda: svc.register_parent(username, password, cnic, code),
                           'Account created! Sign in with your new username and password.')
            st.caption('The code works once and expires after 24 hours. Your school can issue a replacement.')


def show_invitation_code():
    code = st.session_state.get('invitation_code')
    if code:
        st.success('Invitation created. Copy this code and share it privately with the intended guardian.')
        st.html("<div style='color:#c62828;font-size:0.8rem;font-weight:600'>Parent's Invitation Code [Confidential]</div>")
        st.code(code, language=None)
        st.caption('Valid for 24 hours and one registration. The school does not need to choose a parent password.')
        st.download_button('Download invitation slip',
            'SCHOOL DIARY — PARENT INVITATION\n\n'
            'Open the school portal and choose Register as a parent.\n'
            'Enter your chosen username, password, CNIC (13 digits) and this code:\n\n'
            +code+'\n\nUse within 24 hours. Keep this code private.\n',
            file_name='parent_invitation.txt', mime='text/plain')
        if st.button('I have copied the code — hide it'):
            del st.session_state.invitation_code
            st.rerun()


def record_table(uid, kind, records, columns):
    """Sortable table with one explicitly selected record and confirmed actions."""
    if not records:
        st.info('No records yet.')
        return
    table_data = [{label: r[field] for field, label in columns} for r in records]
    # Reset selection if rows/order/status change so it cannot target a different row.
    revision = hashlib.sha256(repr(([r['id'] for r in records], table_data)).encode()).hexdigest()[:12]
    event = st.dataframe(table_data, hide_index=True, **stretch(st.dataframe),
                         key=f'{kind}_table_{revision}', on_select='rerun', selection_mode='single-row')
    selected = event.selection.rows
    st.caption('Select a row using the box on its left to remove or restore that record.')
    if not selected or not 0 <= selected[0] < len(records):
        return
    record = records[selected[0]]
    rid = record['id']
    label = record.get('username', record['name'])
    st.write(f'Selected: {label}')
    if kind=='user' and rid==uid:
        st.caption('Your own administrator account is protected.')
    elif record.get('archived'):
        if st.button('Restore selected record', key=f'restore_{kind}_{rid}'):
            run_action(lambda: svc.restore_record(uid, kind, rid), 'Record restored.')
    elif st.button('× Remove selected record', key=f'remove_{kind}_{rid}'):
        try:
            action = svc.removal_plan(uid, kind, rid)
            st.session_state.pending_removal = (kind, rid, label, action)
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
    confirm_removal(uid)
    show_invitation_code()
    section = st.radio('Administration section', ['Overview', 'Accounts', 'Classes & students',
                        'Parent invitations', 'Link accounts', 'Account access', 'Welcome message'], horizontal=True)
    if section == 'Welcome message':
        message_editor(uid,run_action)
        return
    if section == 'Overview':
        activity_panel(uid)
        return
    account_search = st.text_input('Find account (name or username)',key='admin_account_search') if section in ('Accounts','Classes & students','Link accounts','Account access') else ''
    account_page = int(st.number_input('Account page',min_value=1,value=1,step=1)) if section=='Accounts' else 1
    users = svc.directory(uid,limit=101,offset=(account_page-1)*100,search=account_search) if section in ('Accounts','Classes & students','Link accounts','Account access') else []
    classes = svc.allowed_classes(uid) if section in ('Classes & students','Link accounts') else []
    student_search = st.text_input('Find student (name or ID)',key='admin_student_search') if section in ('Parent invitations','Link accounts') else ''
    students = svc.all_students(uid,limit=101,search=student_search) if section in ('Parent invitations','Link accounts') else []
    if len(users)>100 or len(students)>100:
        st.info('Showing the first 100 matches. Refine your search to find another record.')
    users,students = users[:100],students[:100]
    parents = [u for u in users if u['role']=='parent' and u['active']]
    teachers = [u for u in users if u['role']=='teacher' and u['active']]
    if section == 'Accounts':
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
        account_rows = [dict(u, status='Enabled' if u['active'] else 'Disabled') for u in users]
        record_table(uid, 'user', account_rows,
                     [('id','ID'),('name','Name'),('username','Username'),('role','Role'),('status','Status')])
    if section == 'Classes & students':
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
        roster_search = st.text_input('Search student records',key='roster_search')
        roster_page = int(st.number_input('Student page',min_value=1,value=1,step=1))
        student_rows = [dict(s, status='Archived' if s['archived'] else 'Active')
                        for s in svc.all_students(uid, True,limit=50,offset=(roster_page-1)*50,search=roster_search)]
        record_table(uid, 'student', student_rows,
                     [('student_code','Student ID'),('name','Student name'),('class_name','Class'),('status','Status')])
        st.subheader('Classes')
        class_rows = [dict(c, status='Archived' if c['archived'] else 'Active')
                      for c in svc.allowed_classes(uid, True)]
        record_table(uid, 'class', class_rows, [('id','ID'),('name','Class'),('status','Status')])
    if section == 'Parent invitations':
        st.subheader('Invite a guardian for existing children')
        st.caption('Use this for a second guardian, siblings, or a replacement for an expired/locked invitation. Generating replaces the previous short code for this CNIC. Select every child to link.')
        if students:
            with st.form('new_invitation', clear_on_submit=True):
                selected = select_students('Children to link', students, 'invitation_children')
                name = st.text_input('Guardian name', max_chars=120)
                cnic = st.text_input('CNIC (13 digits)', type='password', max_chars=13)
                if st.form_submit_button('Generate invitation'):
                    run_action(lambda: svc.create_invitation(uid, selected, name, cnic),
                               'Invitation created.', invitation=True)
        invite_page = int(st.number_input('Invitation page', min_value=1, value=1, step=1))
        for invitation in svc.invitations(uid, offset=(invite_page-1)*20):
            row, control = st.columns([10, 2])
            expiry = datetime.fromtimestamp(invitation['expires_at'], svc.KARACHI).strftime('%d %b %Y, %H:%M')
            status=invitation['status']
            color={'Pending':'#c62828','Used':'#16803c'}.get(status,'inherit')
            row.html(f"{html.escape(invitation['guardian_name'])} · {html.escape(invitation['students'])} · "
                         f"<span style='color:{color}'>{html.escape(status)}</span>")
            row.caption(f"Invitation #{invitation['id']} · Expires {expiry} (Pakistan time)")
            if invitation['status'] in ('Pending', 'Locked', 'Expired'):
                if control.button('Revoke', key=f"revoke_{invitation['id']}"):
                    run_action(lambda iid=invitation['id']: svc.revoke_invitation(uid, iid), 'Invitation revoked.')
    if section == 'Link accounts':
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
    if section == 'Account access':
        if not users:
            st.info('No matching account. Change your search.')
            return
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
    if not st.toggle('✏️ Write a diary entry', key=f'write_{cid}'):
        return
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
        with st.container(key=f"reply_card_{comment['id']}"):
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


def toggle_conversation(key):
    st.session_state[key]=not st.session_state.get(key,False)


def show_entry(uid, entry, sid=None):
    eid = entry['id']
    opened_key=f'thread_open_{eid}_{sid}'
    cursor_key=f'comments_cursor_{eid}_{sid}'
    before=st.session_state.get(cursor_key)
    conversation=None
    if st.session_state.get(opened_key,False):
        conversation=svc.conversation_page(uid,eid,sid,before)
        if entry.get('unread_reply_count',0):
            viewed=svc.mark_replies_viewed(uid,eid,sid,[c['id'] for c in conversation[0]])
            entry=dict(entry,unread_reply_count=max(0,entry['unread_reply_count']-viewed))
    with st.container(key=f'feed_card_{eid}_{sid}'):
        st.caption(f"{entry['kind']} · {entry['subject']} · {entry['teacher_name']}")
        st.subheader(entry['title'])
        st.text(entry['body'])
        st.caption(f"Posted: {entry['created_at'][:16].replace('T', ' ')} (Pakistan time)" +
                   (f" | Due / scheduled: {entry['due_date']}" if entry['due_date'] else ''))
        count = entry['reply_count']
        unread=entry.get('unread_reply_count',0)
        opened_key=f'thread_open_{eid}_{sid}'
        with st.container(key=f"reply_indicator_{'new' if unread else 'seen'}_{eid}_{sid}"):
            st.button(f'{count} replies',icon=':material/chat_bubble_outline:',key=f'replies_{eid}_{sid}',
                      help=f'{unread} unseen replies' if unread else 'Show or hide replies',
                      on_click=toggle_conversation,args=(opened_key,))
        st.caption(f"{entry['acknowledged_families']} families acknowledged")
        if sid is not None:
            already_seen = entry['acknowledged_by_me']
            if st.button('✓ Acknowledged' if already_seen else '✓ Acknowledge',
                         key=f'ack_{eid}_{sid}', disabled=already_seen):
                run_action(lambda: svc.acknowledge(uid, eid, sid), 'Acknowledgement saved.')
        if st.session_state.get(opened_key,False):
            st.caption('Guardians of the same child share a thread. Staff can see every family.')
            cursor_key = f'comments_cursor_{eid}_{sid}'
            before = st.session_state.get(cursor_key)
            comments, more, cursor = conversation
            for comment in comments:
                if sid is None:
                    st.caption(f"{comment['child_name']} · {comment['student_code']}")
                comments_view([comment])
            if more and st.button('Older replies',key=f'older_{eid}_{sid}'):
                st.session_state[cursor_key] = cursor
                st.rerun()
            if before is not None and st.button('Latest replies',key=f'latest_{eid}_{sid}'):
                st.session_state.pop(cursor_key,None)
                st.rerun()
            if sid is not None:
                receipts_view(svc.receipts(uid,eid,sid))
                reply_form(uid,eid,sid)
            else:
                roster = svc.entry_roster(uid,eid)
                if roster:
                    selected = choose('Reply / acknowledgements for child',roster,f'family_{eid}','student_code')
                    receipts_view(svc.receipts(uid,eid,selected))
                    if next(s['archived'] for s in roster if s['id']==selected):
                        st.caption('Archived student — read-only.')
                    else:
                        reply_form(uid,eid,selected)


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
    with st.container(key='feed_toolbar'):
        calendar_col,filters_col=st.columns(2)
        with calendar_col:
            with st.popover('',icon=':material/calendar_month:',help='Choose diary dates'):
                mode=st.radio('Selection',['Single day','Date range'],horizontal=True)
                context=f'{uid}_{sid}_{cid}_{mode}'
                value=(svc.today(),svc.today()) if mode=='Date range' else svc.today()
                selected_dates=st.date_input('Posting date',value=value,
                    key=f'diary_dates_{context}',format='DD/MM/YYYY',
                    min_value=date(1900,1,1),max_value=date(2100,12,31))
                dates=(selected_dates,selected_dates) if isinstance(selected_dates,date) else (
                    tuple(selected_dates) if len(selected_dates)==2 else None)
        with filters_col:
            with st.popover('',icon=':material/filter_alt:',help='Filter diary entries'):
                with st.form('feed_filters'):
                    kind=st.selectbox('Type filter',['All']+list(svc.KINDS))
                    search=st.text_input('Search selected dates',max_chars=160)
                    st.form_submit_button('Apply Filter')
                if st.button('Refresh diary'):
                    st.session_state.pop('month_counts',None)
                    st.rerun()
    st.divider()
    st.subheader(':material/menu_book: Diary Feed')
    if dates is None:
        st.info('Choose an end date to display the diary feed.')
        return
    start_date,end_date = dates
    st.caption(f'{start_date:%d %b %Y} → {end_date:%d %b %Y} · Pakistan time')
    signature = (uid,sid,cid,start_date,end_date,kind,search)
    if st.session_state.get('feed_signature') != signature:
        st.session_state.feed_signature = signature
        st.session_state.feed_page = 0
    page = st.session_state.get('feed_page',0)
    entries,more = svc.feed_page(uid,sid,cid,start_date,end_date,page,kind,search)
    if not entries:
        st.info('No matching entries for these dates.')
    for entry in entries:
        show_entry(uid,entry,sid)
    prev,next_col = st.columns(2)
    if prev.button('Newer posts',disabled=page==0):
        st.session_state.feed_page = page-1
        st.rerun()
    if next_col.button('Older posts',disabled=not more):
        st.session_state.feed_page = page+1
        st.rerun()
    st.caption(f'Page {page+1} · Up to 10 posts')


def activity_panel(uid):
    st.subheader('Activity Log')
    st.caption('Recent school activity · Refresh for updates · Pakistan time')
    before = st.session_state.get('activity_before')
    rows = svc.activity(uid,before)
    with st.container(border=True,height=420):
        if not rows:
            st.info('New activity will appear here after this update.')
        for row in rows[:50]:
            st.text(f"{row['created_at'][:16].replace('T',' ')}  |  {row['actor_name']}  |  {row['action']}")
    a,b = st.columns(2)
    if a.button('Refresh / latest activity'):
        st.session_state.pop('activity_before',None)
        st.rerun()
    if b.button('Older activity',disabled=len(rows)<=50):
        st.session_state.activity_before = rows[49]['id']
        st.rerun()


def main():
    # Establish the sidebar before remote database reads shift the main layout.
    st.sidebar.title('📖 School Diary')
    init_db()
    render_welcome()
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
    with svc.read_scope():
        main()
except SQLAlchemyError:
    st.error('The database is temporarily unavailable. Please refresh and try again.')
except (ValueError, PermissionError) as exc:
    st.error(str(exc))



