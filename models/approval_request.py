# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    # Add procurement-specific fields
    price_unit = fields.Float('Unit Price', default=0.0)
    vendor_id = fields.Many2one('res.partner', string='Preferred Vendor',
                                domain=[('is_company', '=', True), ('supplier_rank', '>', 0)])
    seller_id = fields.Many2one('product.supplierinfo', string='Supplier Info',
                                help="Supplier information for RFQ creation")
    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange('vendor_id', 'product_id')
    def _onchange_vendor_product(self):
        """Update seller_id when vendor or product changes"""
        if self.vendor_id and self.product_id:
            # Find existing supplier info or prepare for creation
            supplier_info = self.env['product.supplierinfo'].search([
                ('partner_id', '=', self.vendor_id.id),
                ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)
            ], limit=1)

            if supplier_info:
                self.seller_id = supplier_info.id
            else:
                # Clear seller_id if no supplier info exists
                # It will be created when the request is submitted
                self.seller_id = False


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    # Stock requisition fields
    source_location_id = fields.Many2one('stock.location', string='Source Location',
                                        domain="[('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])]",
                                        help="Location where products will be taken from")
    dest_location_id = fields.Many2one('stock.location', string='Destination Location',
                                      domain="[('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])]",
                                      help="Location where products will be delivered")
    stock_picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True,
                                      help="Internal transfer created from this request")
    picking_state = fields.Selection(related='stock_picking_id.state', string='Transfer Status', readonly=True)
    stock_availability_checked = fields.Boolean('Stock Checked', default=False,
                                               help="Whether stock availability has been verified")

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
        """Override to handle purchase order and stock picking creation"""
        res = super().action_approve()

        for request in self:
            if request.request_status == 'approved':
                # Handle purchase-type approvals (RFQ creation)
                if (request.category_id.approval_type == 'purchase' and
                    request.partner_id):

                    # Check if we have the approvals_purchase addon functionality
                    if (hasattr(request, 'action_create_purchase_orders') and
                        request.product_line_ids):
                        # Use the standard approvals_purchase flow if available
                        try:
                            request.action_create_purchase_orders()
                        except Exception:
                            # Fallback to our custom method if there's an issue
                            request._create_purchase_order()
                    else:
                        # Use our custom method for non-purchase type categories
                        request._create_purchase_order()

                # Handle stock requisition approvals
                elif (request.category_id.name == 'Stock Requisition' and
                      request.source_location_id and request.dest_location_id and
                      request.product_line_ids and not request.stock_picking_id):
                    request._create_stock_transfer()

        return res

    def _create_purchase_order(self):
        """Create purchase order from approved request (fallback method)"""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_('Please specify a vendor before creating purchase order.'))

        # Ensure product lines have proper vendor information for purchase
        for line in self.product_line_ids:
            if line.product_id and not line.product_id.seller_ids:
                # Create supplier info for the product if it doesn't exist
                self.env['product.supplierinfo'].sudo().create({
                    'partner_id': self.partner_id.id,
                    'product_tmpl_id': line.product_id.product_tmpl_id.id,
                    'min_qty': 1,
                    'price': line.product_id.standard_price or 0,
                    'company_id': self.company_id.id,
                })

        po_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'currency_id': self.company_id.currency_id.id,
        }

        # Create purchase order lines
        order_lines = []
        if self.product_line_ids:
            for line in self.product_line_ids:
                if line.product_id:
                    # Use proper purchase order line creation
                    order_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.description or line.product_id.name,
                        'product_qty': line.quantity,
                        'product_uom': line.product_id.sudo().uom_po_id.id,
                        'price_unit': line.product_id.standard_price or 0,
                        'date_planned': fields.Datetime.now(),
                    }))
                else:
                    # For products without ID (custom descriptions)
                    order_lines.append((0, 0, {
                        'name': line.description,
                        'product_qty': line.quantity,
                        'product_uom': 1,  # Units
                        'price_unit': 0,
                        'date_planned': fields.Datetime.now(),
                    }))
        elif self.amount:
            # Generic line for amount-based requests
            order_lines.append((0, 0, {
                'name': self.name,
                'product_qty': self.quantity or 1,
                'product_uom': 1,
                'price_unit': self.amount,
                'date_planned': fields.Datetime.now(),
            }))

        po_vals['order_line'] = order_lines

        purchase_order = self.env['purchase.order'].create(po_vals)
        self.purchase_order_id = purchase_order.id

        # Link quotation attachments to the purchase order
        quotation_attachments = self.attachment_ids.filtered(
            lambda att: att.description == 'Quotation'
        )
        for attachment in quotation_attachments:
            attachment.copy({
                'res_model': 'purchase.order',
                'res_id': purchase_order.id,
                'name': f"Quotation - {attachment.name}",
            })

        # Post message about PO creation with links to quotations
        message_body = _('Purchase Order %s created from this approval request.') % purchase_order.name
        if quotation_attachments:
            message_body += _('<br/>Quotations have been linked to the purchase order.')

        self.message_post(
            body=message_body,
            message_type='notification'
        )

        return purchase_order

    def _create_stock_transfer(self):
        """Create internal stock transfer from approved request"""
        self.ensure_one()

        if not self.source_location_id or not self.dest_location_id:
            raise UserError(_('Source and destination locations are required for stock requisition.'))

        if not self.product_line_ids:
            raise UserError(_('At least one product line is required for stock requisition.'))

        # Check product availability first
        self._check_stock_availability()

        # Get internal picking type
        internal_picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not internal_picking_type:
            raise UserError(_('No internal picking type found for company %s') % self.company_id.name)

        # Create stock picking
        picking_vals = {
            'picking_type_id': internal_picking_type.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': f'Stock Requisition: {self.name}',
            'company_id': self.company_id.id,
            'move_type': 'direct',
            'partner_id': self.employee_id.work_contact_id.id if self.employee_id.work_contact_id else False,
        }

        picking = self.env['stock.picking'].create(picking_vals)

        # Create stock moves for each product line
        for line in self.product_line_ids:
            if line.product_id and line.quantity > 0:
                move_vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.sudo().uom_id.id,
                    'picking_id': picking.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.dest_location_id.id,
                    'company_id': self.company_id.id,
                }
                self.env['stock.move'].create(move_vals)

        # Link the picking to this request
        self.stock_picking_id = picking.id

        # Confirm the picking and try to assign stock
        picking.action_confirm()
        picking.action_assign()

        # Post message about stock transfer creation
        self.message_post(
            body=_('Internal Transfer %s created from this stock requisition request.') % picking.name,
            message_type='notification'
        )

        return picking

    def _check_stock_availability(self):
        """Check if requested products are available in source location"""
        self.ensure_one()

        unavailable_products = []

        for line in self.product_line_ids:
            if line.product_id and line.quantity > 0:
                # Check available quantity in source location
                available_qty = self.env['stock.quant']._get_available_quantity(
                    line.product_id,
                    self.source_location_id,
                    strict=True
                )

                if available_qty < line.quantity:
                    unavailable_products.append({
                        'product': line.product_id.name,
                        'requested': line.quantity,
                        'available': available_qty,
                    })

        if unavailable_products:
            error_msg = _('Insufficient stock available:\n')
            for item in unavailable_products:
                error_msg += _('• %s: Requested %.2f, Available %.2f\n') % (
                    item['product'], item['requested'], item['available']
                )
            raise UserError(error_msg)

        # Mark stock as checked
        self.stock_availability_checked = True

    def action_check_stock_availability(self):
        """Manual action to check stock availability"""
        self.ensure_one()
        try:
            self._check_stock_availability()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Stock Check'),
                    'message': _('All requested products are available in the source location.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Stock Check Failed'),
                    'message': str(e),
                    'type': 'warning',
                    'sticky': True,
                }
            }

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