# -*- coding: utf-8 -*-
{
    'name': 'Platinum Project - Portal Approvals',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Approvals',
    'summary': 'Employee portal interface for approval requests',
    'description': """
Platinum Project - Portal Approvals
====================================

This module extends the standard Odoo approvals functionality to provide:
- Portal access for employees to submit approval requests
- Employee-based request ownership (not just users)
- Mobile-responsive portal interface
- Budget tracking integration
- Streamlined approval workflows

Key Features:
- Employees can submit requests via portal without backend access
- Real-time budget validation before submission
- Department-based approval routing
- Email notifications at each step
- Complete audit trail and tracking
    """,
    'depends': [
        'approvals',      # Core approval functionality
        'hr',             # Employee data and departments
        'portal',         # Portal access framework
        'purchase',       # Purchase order integration
        'stock',          # Inventory management
        'account',        # Budget tracking via analytic accounts
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/portal_security.xml',

        # Data
        'data/cron_link_users.xml',
        # 'data/approval_categories.xml',

        # Views
        'views/approval_request_views.xml',
        'views/hr_employee_views.xml',
        'views/portal_templates.xml',

        # Menu items
        'views/portal_menu.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'platinum_proj/static/src/js/portal_form.js',
            'platinum_proj/static/src/scss/portal_style.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}

