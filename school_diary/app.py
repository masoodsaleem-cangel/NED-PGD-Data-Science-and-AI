"""Run: python -m streamlit run app.py"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import service as svc
from db import init_db, query

st.set_page_config(page_title='School Diary', page_icon='📖', layout='wide')
st.markdown('''<style>
.stApp {background:#f6f7fb;}
h1,h2,h3 {color:#44305d;}
[data-testid="stMetric"] {background:white;padding:18px;border-radius:14px;}
</style>''', unsafe_allow_html=True)
init_db()


def choose(label, rows, key, field='name'):
    return st.selectbox(label, [r['id'] for r in rows],
                        format_func=lambda x: next(r[field] for r in rows if r['id']==x), key=key)


def save(action):
    try:
        action()
        st.success('Saved successfully.')
    except IntegrityError:
        st.error('This record already exists, or a required linked record is missing.')
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        st.error('The database could not save this change. Check the connection and try again.')


def login_screen():
    st.title('📖 School Diary')
    st.write('A daily connection between school and home.')
    _, middle, _ = st.columns([1,2,1])
    with middle:
        role_label = st.radio('Sign in as', ['Parent','Teacher','Super admin'], horizontal=True)
        role = {'Parent':'parent','Teacher':'teacher','Super admin':'admin'}[role_label]
        with st.form('login'):
            identifier = st.text_input('Student ID' if role=='parent' else 'Username')
            cnic = st.text_input('Parent CNIC', type='password', placeholder='00000-0000000-0') if role=='parent' else ''
            password = st.text_input('Password',type='password')
            submitted = st.form_submit_button('Sign in',use_container_width=True)
        if submitted:
            user = svc.login(role,identifier,password,cnic)
            if user:
                st.session_state.clear()
                st.session_state.user_id=user['id']
                st.session_state.last_activity=time.time()
                st.rerun()
            st.error('Sign-in failed. Check your details, or wait 5 minutes if your account is locked.')
        st.caption('Parents: use a linked child’s student ID, your registered CNIC, and your password.')
        if not query('SELECT id FROM users LIMIT 1'):
            st.info('First run: stop the app and run python setup.py --demo for sample data, or python setup.py for an empty school.')


def admin_panel(uid):
    st.header('School administration')
    users=svc.directory(uid)
    classes=svc.allowed_classes(uid)
    students=query('SELECT id,student_code,name,class_id FROM students ORDER BY name')
    tabs=st.tabs(['Overview','People','Classes & students','Link accounts','Account access'])
    with tabs[0]:
        cols=st.columns(3)
        cols[0].metric('Students',len(students))
        cols[1].metric('Classes',len(classes))
        cols[2].metric('Teachers',sum(u['role']=='teacher' for u in users))
        st.subheader('School directory')
        st.dataframe(users,use_container_width=True,hide_index=True)
        st.caption('CNICs and password hashes are never displayed in this directory.')
    with tabs[1]:
        role=st.selectbox('New account type',['teacher','parent','admin'])
        with st.form('new_user',clear_on_submit=True):
            name=st.text_input('Full name')
            username=st.text_input('Unique account username')
            password=st.text_input('Initial password (10+ characters)',type='password')
            cnic=st.text_input('CNIC (parents only)',type='password') if role=='parent' else ''
            if st.form_submit_button('Create account'):
                save(lambda:svc.create_user(uid,name,username,role,password,cnic))
        st.caption('Share credentials privately. Parents use student ID + CNIC + password to sign in.')
    with tabs[2]:
        with st.form('new_class',clear_on_submit=True):
            name=st.text_input('Class and section',placeholder='Grade 3 • A')
            if st.form_submit_button('Add class'):
                save(lambda:svc.add_class(uid,name))
        if classes:
            with st.form('new_student',clear_on_submit=True):
                code=st.text_input('Student ID',placeholder='ST-2026-001')
                name=st.text_input('Student name')
                class_id=choose('Class',classes,'student_class')
                if st.form_submit_button('Add student'):
                    save(lambda:svc.add_student(uid,code,name,class_id))
        st.dataframe(students,use_container_width=True,hide_index=True)
    with tabs[3]:
        parents=[u for u in users if u['role']=='parent']
        teachers=[u for u in users if u['role']=='teacher']
        if students and parents:
            with st.form('link_parent'):
                sid=choose('Student',students,'link_student',field='student_code')
                pid=choose('Parent',parents,'link_parent_id',field='username')
                if st.form_submit_button('Link parent to student'):
                    save(lambda:svc.link_parent(uid,sid,pid))
        else:
            st.info('Create a parent and student before linking them.')
        if teachers and classes:
            with st.form('assign_teacher'):
                tid=choose('Teacher',teachers,'assign_teacher_id',field='username')
                cid=choose('Assigned class',classes,'assigned_class')
                if st.form_submit_button('Assign teacher'):
                    save(lambda:svc.assign_teacher(uid,tid,cid))
        st.subheader('Current links')
        st.dataframe(query('''SELECT s.student_code,u.username AS parent FROM student_parents sp
            JOIN students s ON s.id=sp.student_id JOIN users u ON u.id=sp.parent_id'''),hide_index=True)
        st.dataframe(query('''SELECT u.username AS teacher,c.name AS class FROM teacher_classes tc
            JOIN users u ON u.id=tc.teacher_id JOIN classes c ON c.id=tc.class_id'''),hide_index=True)
    with tabs[4]:
        target=choose('Account',users,'account_target',field='username')
        with st.form('reset_password'):
            new=st.text_input('New password',type='password')
            if st.form_submit_button('Reset password'):
                save(lambda:svc.reset_password(uid,target,new))
        active=st.checkbox('Account enabled',value=bool(next(u['active'] for u in users if u['id']==target)),key=f'enabled_{target}')
        if st.button('Save account status'):
            save(lambda:svc.set_active(uid,target,active))
    if st.button('Refresh school records'):
        st.rerun()


def compose(uid,cid):
    roster=svc.class_students(uid,cid)
    with st.form('compose',clear_on_submit=True):
        st.subheader('Write a diary entry')
        kind=st.selectbox('Type',['Homework','Notice','Activity','Private note'])
        sid=st.selectbox('Audience',[None]+[s['id'] for s in roster],
            format_func=lambda x:'Whole class' if x is None else next(f"{s['name']} ({s['student_code']})" for s in roster if s['id']==x))
        subject=st.text_input('Subject',placeholder='Mathematics / General')
        title=st.text_input('Title')
        body=st.text_area('Instructions or message',height=130)
        has_due=st.checkbox('Include a due date / activity date')
        due=st.date_input('Date',value=datetime.now(ZoneInfo('Asia/Karachi')).date())
        if st.form_submit_button('Publish entry',type='primary'):
            save(lambda:svc.create_entry(uid,cid,sid,kind,subject,title,body,due if has_due else None))


def show_entry(uid,e,sid,parent):
    with st.container(border=True):
        st.caption(f"{e['kind']} · {e['subject']} · {e['teacher_name']}")
        st.subheader(e['title'])
        st.text(e['body'])
        st.caption(f"Posted: {e['created_at'][:16].replace('T',' ')} (Pakistan time)" +
                   (f" | Due / scheduled: {e['due_date']}" if e['due_date'] else ''))
        if sid is None:
            st.info('No students in this class yet.')
            return
        receipts=svc.receipts(uid,e['id'],sid)
        if parent:
            if st.button('✓ Acknowledge',key=f"ack_{e['id']}_{sid}"):
                save(lambda:svc.acknowledge(uid,e['id'],sid))
                receipts=svc.receipts(uid,e['id'],sid)
        if receipts:
            st.caption('Acknowledged by: '+', '.join(r['name'] for r in receipts))
        with st.expander('Private conversation with this student’s family'):
            for r in svc.thread(uid,e['id'],sid):
                st.caption(f"{r['name']} ({r['role']}) · {r['created_at'][:16].replace('T',' ')}")
                st.text(r['body'])
            with st.form(f"reply_{e['id']}_{sid}",clear_on_submit=True):
                body=st.text_area('Reply',key=f"text_{e['id']}_{sid}")
                if st.form_submit_button('Send reply'):
                    try:
                        svc.reply(uid,e['id'],sid,body)
                        st.rerun()
                    except (ValueError,PermissionError) as exc:
                        st.error(str(exc))


def diary_panel(uid,role):
    parent=role=='parent'
    if parent:
        kids=svc.children(uid)
        if not kids:
            st.info('Ask the school administrator to link your child to your account.')
            return
        sid=choose('Your child',kids,'child')
        student=next(s for s in kids if s['id']==sid)
        st.header(f"{student['name']}’s diary")
        st.caption(f"{student['student_code']} · {student['class_name']}")
        entries=svc.diary(uid,student_id=sid)
    else:
        classes=svc.allowed_classes(uid)
        if not classes:
            st.info('No classes assigned yet. Please contact the administrator.')
            return
        cid=choose('Class',classes,'diary_class')
        compose(uid,cid)
        entries=svc.diary(uid,class_id=cid)
        roster=svc.class_students(uid,cid)
    st.subheader('Diary feed')
    kind=st.selectbox('Filter',['All','Homework','Notice','Activity','Private note'])
    search=st.text_input('Search diary')
    entries=[e for e in entries if (kind=='All' or e['kind']==kind) and
             search.lower() in (e['title']+' '+e['body']+' '+e['subject']).lower()]
    st.caption(f'{len(entries)} entries')
    for e in entries:
        if not parent:
            options=[s for s in roster if e['student_id'] in (None,s['id'])]
            st.caption('Private student note' if e['student_id'] else 'Whole-class entry')
            sid=choose('View acknowledgement and conversation for',options,f"thread_student_{e['id']}") if options else None
        show_entry(uid,e,sid,parent)


if 'user_id' not in st.session_state:
    login_screen()
    st.stop()
if time.time()-st.session_state.get('last_activity',0)>1800:
    st.session_state.clear()
    st.rerun()
try:
    user=svc.actor(st.session_state.user_id)
except PermissionError:
    st.session_state.clear()
    st.rerun()
st.session_state.last_activity=time.time()
uid=user['id']
st.sidebar.title('📖 School Diary')
st.sidebar.write(user['name'])
st.sidebar.caption({'admin':'Super admin','teacher':'Teacher','parent':'Parent'}[user['role']])
options=(['Administration'] if user['role']=='admin' else [])+['Diary','My password']
page=st.sidebar.radio('Menu',options)
if st.sidebar.button('Sign out'):
    st.session_state.clear()
    st.rerun()
if page=='Administration':
    admin_panel(uid)
elif page=='Diary':
    diary_panel(uid,user['role'])
else:
    st.header('Change password')
    with st.form('my_password',clear_on_submit=True):
        old=st.text_input('Current password',type='password')
        new=st.text_input('New password (10+ characters)',type='password')
        if st.form_submit_button('Change password'):
            save(lambda:svc.change_password(uid,old,new))
