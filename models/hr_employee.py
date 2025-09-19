# -*- coding: utf-8 -*-

from odoo import fields, models, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Approval-related fields
    approval_request_ids = fields.One2many(
        'approval.request',
        'employee_id',
        string='Approval Requests'
    )

    approval_request_count = fields.Integer(
        string='Approval Requests Count',
        compute='_compute_approval_request_count'
    )

    @api.depends('approval_request_ids')
    def _compute_approval_request_count(self):
        """Count approval requests for this employee"""
        for employee in self:
            employee.approval_request_count = len(employee.approval_request_ids)

    def action_view_approval_requests(self):
        """View approval requests for this employee"""
        self.ensure_one()
        return {
            'name': f'Approval Requests - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'approval.request',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_request_owner_id': self.user_id.id if self.user_id else False,
            }
        }

    @api.model
    def link_portal_users(self):
        """Simple method to link portal users to employees by email"""
        # Find employees with work_email but no user_id
        employees_without_user = self.search([
            ('work_email', '!=', False),
            ('user_id', '=', False)
        ])

        linked_count = 0
        for employee in employees_without_user:
            # Look for portal user with matching email
            portal_user = self.env['res.users'].search([
                ('email', '=', employee.work_email),
                ('share', '=', True),  # Portal user
            ], limit=1)

            if portal_user:
                # Link them together
                employee.user_id = portal_user.id
                linked_count += 1

        return f"Linked {linked_count} employees to portal users"