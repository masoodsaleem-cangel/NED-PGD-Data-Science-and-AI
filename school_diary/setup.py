"""Initialize an empty school, or explicitly load fictional demonstration data."""
import argparse
from getpass import getpass
from datetime import date, timedelta
from db import init_db, query
from service import (_create_user, add_class, add_student, link_parent,
                     assign_teacher, create_entry)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true',help='Load fictional demo accounts')
    args=parser.parse_args()
    init_db()
    if query('SELECT id FROM users LIMIT 1'):
        raise SystemExit('Database already has accounts. Nothing changed.')
    if not args.demo:
        name=input('Admin full name: ').strip()
        username=input('Admin username: ').strip()
        password=getpass('Admin password (10+ characters): ')
        _create_user(name,username,'admin',password)
        print('Admin created. Run: python -m streamlit run app.py')
        return
    admin=_create_user('Demo Administrator','admin','admin','AdminDemo!2026')
    teacher=_create_user('Ms Sara (demo)','teacher','teacher','TeacherDemo!2026')
    parent=_create_user('Demo Parent','parent','parent','ParentDemo!2026','00000-0000000-1')
    other=_create_user('Other Demo Parent','parent2','parent','ParentDemo!2026','00000-0000000-2')
    c1=add_class(admin,'Grade 3 • A')
    c2=add_class(admin,'Grade 5 • B')
    s1=add_student(admin,'ST-001','Hina (demo)',c1)
    s2=add_student(admin,'ST-002','Ali (demo)',c2)
    s3=add_student(admin,'ST-003','Bilal (demo)',c1)
    link_parent(admin,s1,parent)
    link_parent(admin,s2,parent)
    link_parent(admin,s3,other)
    assign_teacher(admin,teacher,c1)
    assign_teacher(admin,teacher,c2)
    due=(date.today()+timedelta(days=2)).isoformat()
    create_entry(teacher,c1,None,'Homework','Mathematics','Practice multiplication',
                 'Complete questions 1–5 on page 24. Please sign the exercise book.',due)
    create_entry(teacher,c1,None,'Activity','General','Science day',
                 'Bring one small recycled item for our classroom science activity.',due)
    create_entry(teacher,c1,s1,'Private note','General','A lovely effort today',
                 'Hina helped a classmate with reading today. Thank you for practising at home.')
    create_entry(teacher,c2,None,'Notice','English','Reading week',
                 'Please read one short story together and discuss your favourite character.',due)
    print('Fictional demo ready. See README.md for logins. Never use demo credentials for a real school.')

if __name__=='__main__':
    main()
