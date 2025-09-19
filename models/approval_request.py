# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def _get_request_owner_id_domain(self):
        """Override to allow both internal and portal users"""
        # Allow both internal users (share=False) and portal users (share=True)
        # who are linked to employees
        employee_user_ids = self.env['hr.employee'].search([
            ('user_id', '!=', False)
        ]).mapped('user_id.id')

        return [
            '|',
            ('share', '=', False),  # Internal users
            '&', ('share', '=', True), ('id', 'in', employee_user_ids)  # Portal users linked to employees
        ]

    # Link to employee instead of just user for better portal integration
    employee_id = fields.Many2one(
        'hr.employee',
        string='Requesting Employee',
        compute='_compute_employee_id',
        store=True,
        readonly=False
    )

    # Budget tracking fields
    budget_line_id = fields.Many2one(
        'account.analytic.account',
        string='Budget Category',
        help='Analytic account used for budget tracking'
    )

    # Purchase order integration
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        readonly=True,
        help='Purchase order created from this approval request'
    )

    # Portal-specific fields
    portal_submission = fields.Boolean(
        string='Submitted via Portal',
        default=False,
        help='Indicates if this request was submitted through the employee portal'
    )

    # Employee manager for approval routing
    manager_employee_id = fields.Many2one(
        'hr.employee',
        string='Manager',
        related='employee_id.parent_id',
        store=True,
        readonly=True
    )

    @api.depends('request_owner_id')
    def _compute_employee_id(self):
        """Compute employee based on request owner"""
        for request in self:
            if request.request_owner_id:
                # First try direct user_id link (for internal users)
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', request.request_owner_id.id)
                ], limit=1)

                # If not found, try email matching (for portal users)
                if not employee and request.request_owner_id.email:
                    employee = self.env['hr.employee'].search([
                        ('work_email', '=', request.request_owner_id.email)
                    ], limit=1)

                request.employee_id = employee.id if employee else False
            else:
                request.employee_id = False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle portal submissions"""
        for vals in vals_list:
            # Check if this is a portal submission
            if self.env.context.get('portal_submission'):
                vals['portal_submission'] = True

            # Auto-assign employee if not set
            if not vals.get('employee_id') and vals.get('request_owner_id'):
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', vals['request_owner_id'])
                ], limit=1)
                if employee:
                    vals['employee_id'] = employee.id

        return super().create(vals_list)

    def action_approve(self):
        """Override to handle purchase order creation"""
        res = super().action_approve()

        for request in self:
            if (request.request_status == 'approved' and
                request.category_id.approval_type == 'purchase' and
                not request.purchase_order_id):
                request._create_purchase_order()

        return res

    def _create_purchase_order(self):
        """Create purchase order from approved request"""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_('Please specify a vendor before creating purchase order.'))

        po_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'currency_id': self.company_id.currency_id.id,
        }

        # Create purchase order lines if product information is available
        order_lines = []
        if hasattr(self, 'product_line_ids') and self.product_line_ids:
            for line in self.product_line_ids:
                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity,
                    'price_unit': line.product_id.standard_price,
                    'date_planned': fields.Datetime.now(),
                }))
        else:
            # If no specific products, create a generic line
            if self.amount:
                order_lines.append((0, 0, {
                    'name': self.name,
                    'product_qty': 1,
                    'price_unit': self.amount,
                    'date_planned': fields.Datetime.now(),
                }))

        po_vals['order_line'] = order_lines

        purchase_order = self.env['purchase.order'].create(po_vals)
        self.purchase_order_id = purchase_order.id

        # Post message about PO creation
        self.message_post(
            body=_('Purchase Order %s created from this approval request.') % purchase_order.name,
            message_type='notification'
        )

        return purchase_order

    def _check_budget_availability(self):
        """Check if budget is available for this request"""
        if not self.budget_line_id or not self.amount:
            return True

        # Get current month's spending for this budget category
        domain = [
            ('budget_line_id', '=', self.budget_line_id.id),
            ('request_status', '=', 'approved'),
            ('create_date', '>=', fields.Datetime.now().replace(day=1)),
            ('id', '!=', self.id)  # Exclude current request
        ]

        spent_amount = sum(
            self.search(domain).mapped('amount')
        )

        available_budget = self.budget_line_id.budget or 0
        return (spent_amount + self.amount) <= available_budget

    @api.constrains('amount', 'budget_line_id')
    def _validate_budget(self):
        """Validate budget constraints"""
        for request in self:
            if request.amount and request.budget_line_id:
                if not request._check_budget_availability():
                    raise UserError(_(
                        'Insufficient budget for category %s. '
                        'Request amount exceeds available budget.'
                    ) % request.budget_line_id.name)

    def action_confirm(self):
        """Override confirm action for portal-specific logic"""
        # Validate budget before confirmation
        for request in self:
            if not request._check_budget_availability():
                raise UserError(_(
                    'Cannot submit request: insufficient budget available for %s'
                ) % (request.budget_line_id.name or 'this category'))

        return super().action_confirm()

    def get_portal_url(self, suffix=None, report_type=None, download=None, query_string=None):
        """Get portal URL for this approval request"""
        self.ensure_one()
        return f'/my/approval/{self.id}'

    def action_view_purchase_order(self):
        """View related purchase order"""
        self.ensure_one()
        if self.purchase_order_id:
            return {
                'name': _('Purchase Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': self.purchase_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False