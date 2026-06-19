{
    'name': 'Attendance Import Swipe Wizard',
    'version': '18.0.1.0.0',
    'summary': 'Import card swipe attendance CSV',
    'category': 'Human Resources',
    'depends': ['hr_attendance','resource','report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        'report/report.xml',
        'views/attendance_category.xml',
        'views/attendance_import_view.xml',
        "views/hr_attendance_view.xml",
        "wizard/attendance.xml",
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}