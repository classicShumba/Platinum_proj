# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools import groupby as groupbyelem
from collections import OrderedDict
import logging
import base64

_logger = logging.getLogger(__name__)




class EmployeePortal(CustomerPortal):

    @http.route()
    def home(self, **kw):
        """Override portal home to include approval counts"""
        return super().home(**kw)

    def _prepare_home_portal_values(self, counters):
        """Add approval requests to portal counters"""
        values = super()._prepare_home_portal_values(counters)

        # Check if current user is an employee
        is_employee_user = self._is_employee_user()
        values['is_employee_user'] = is_employee_user

        # Add approval count only for employee users
        if is_employee_user:
            try:
                approval_count = request.env['approval.request'].search_count([
                    ('request_owner_id', '=', request.env.user.id)
                ])
                values['approval_count'] = approval_count
            except:
                values['approval_count'] = 0
        else:
            values['approval_count'] = 0

        return values

    def _is_employee_user(self):
        """Check if current user is linked to an employee record"""
        if not request.env.user or request.env.user._is_public():
            _logger.info(f"User check failed: user={request.env.user}, is_public={request.env.user._is_public() if request.env.user else 'No user'}")
            return False

        user_id = request.env.user.id
        user_email = request.env.user.email

        # Check if user has employee record (direct link or email match)
        employee = request.env['hr.employee'].search([
            '|',
            ('user_id', '=', user_id),
            ('work_email', '=', user_email)
        ], limit=1)

        _logger.info(f"Employee check for user {user_id} ({user_email}): employee found={bool(employee)}")
        if employee:
            _logger.info(f"Employee found: {employee.name} (id={employee.id})")

        return bool(employee)

    def _get_approval_domain(self):
        """Get domain for user's approval requests"""
        return [('request_owner_id', '=', request.env.user.id)]

    @http.route(['/my/approvals', '/my/approvals/page/<int:page>'],
                type='http', auth="user", website=True)
    def portal_my_approvals(self, page=1, date_begin=None, date_end=None,
                           sortby=None, search=None, search_in='content',
                           groupby='none', filterby='all', **kw):
        """Employee portal page for approval requests"""
        # Check if user is an employee
        if not self._is_employee_user():
            _logger.info(f"Access denied to /my/approvals for user {request.env.user.id} - not an employee")
            return request.redirect('/my')

        values = self._prepare_portal_layout_values()
        ApprovalRequest = request.env['approval.request']

        domain = self._get_approval_domain()

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Subject'), 'order': 'name'},
            'status': {'label': _('Status'), 'order': 'request_status'},
        }

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'new': {'label': _('New'), 'domain': [('request_status', '=', 'new')]},
            'pending': {'label': _('Pending'), 'domain': [('request_status', '=', 'pending')]},
            'approved': {'label': _('Approved'), 'domain': [('request_status', '=', 'approved')]},
            'refused': {'label': _('Refused'), 'domain': [('request_status', '=', 'refused')]},
        }

        searchbar_inputs = {
            'content': {'input': 'content', 'label': _('Search <span class="nolabel"> (in Content)</span>')},
            'name': {'input': 'name', 'label': _('Search in Subject')},
            'status': {'input': 'status', 'label': _('Search in Status')},
        }

        searchbar_groupby = {
            'none': {'input': 'none', 'label': _('None')},
            'status': {'input': 'status', 'label': _('Status')},
            'category': {'input': 'category_id', 'label': _('Category')},
        }

        # default sort
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # default filter
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # search
        if search and search_in:
            search_domain = []
            if search_in in ('content', 'all'):
                search_domain = ['|', ('name', 'ilike', search), ('reason', 'ilike', search)]
            elif search_in == 'name':
                search_domain = [('name', 'ilike', search)]
            elif search_in == 'status':
                search_domain = [('request_status', 'ilike', search)]
            domain += search_domain

        # count for pager
        approval_count = ApprovalRequest.search_count(domain)

        # pager
        pager = portal_pager(
            url="/my/approvals",
            url_args={'date_begin': date_begin, 'date_end': date_end,
                     'sortby': sortby, 'groupby': groupby, 'search_in': search_in,
                     'search': search, 'filterby': filterby},
            total=approval_count,
            page=page,
            step=self._items_per_page
        )

        # content according to pager and archive selected
        approvals = ApprovalRequest.search(domain, order=order,
                                         limit=self._items_per_page,
                                         offset=pager['offset'])
        request.session['my_approvals_history'] = approvals.ids[:100]

        groupby_mapping = {
            'status': 'request_status',
            'category': 'category_id',
        }

        if groupby in groupby_mapping:
            grouped_approvals = [
                ApprovalRequest.concat(*g)
                for k, g in groupbyelem(approvals, itemgetter=lambda x: x[groupby_mapping[groupby]])
            ]
        else:
            grouped_approvals = [approvals]

        values.update({
            'date': date_begin,
            'date_end': date_end,
            'grouped_approvals': grouped_approvals,
            'page_name': 'approval',
            'archive_groups': [],
            'default_url': '/my/approvals',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'search': search,
            'sortby': sortby,
            'groupby': groupby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
        })
        return request.render("platinum_proj.portal_my_approvals", values)

    @http.route(['/my/approval/<int:approval_id>'], type='http', auth="user", website=True)
    def portal_approval_detail(self, approval_id, access_token=None, **kw):
        """Detail view for specific approval request"""
        try:
            approval_sudo = self._document_check_access('approval.request',
                                                       approval_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = {
            'approval': approval_sudo,
            'page_name': 'approval',
        }
        return request.render("platinum_proj.portal_approval_detail", values)

    @http.route(['/my/approval/edit/<int:approval_id>'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_approval_edit(self, approval_id, access_token=None, **post):
        """Edit an existing approval request (only if pending)"""
        try:
            approval_sudo = self._document_check_access('approval.request',
                                                       approval_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # Only allow editing if request is in editable state
        if approval_sudo.request_status not in ['new', 'pending']:
            return request.redirect(f'/my/approval/{approval_id}')

        category = approval_sudo.category_id

        if request.httprequest.method == 'POST':
            # Process form submission for edit
            vals = {}

            # Update fields only if provided, otherwise keep existing
            if post.get('name'):
                vals['name'] = post.get('name')
            if post.get('reason'):
                vals['reason'] = post.get('reason')
            if post.get('amount'):
                vals['amount'] = float(post.get('amount'))
            if post.get('quantity'):
                vals['quantity'] = float(post.get('quantity'))
            if post.get('location'):
                vals['location'] = post.get('location')
            if post.get('reference'):
                vals['reference'] = post.get('reference')
            if post.get('partner_id'):
                vals['partner_id'] = int(post.get('partner_id'))
            if post.get('date'):
                vals['date'] = fields.Datetime.from_string(post.get('date'))
            if post.get('date_start'):
                vals['date_start'] = fields.Datetime.from_string(post.get('date_start'))
            if post.get('date_end'):
                vals['date_end'] = fields.Datetime.from_string(post.get('date_end'))

            # Handle product lines
            approval_sudo.product_line_ids.unlink()  # Clear existing
            product_lines = []

            product_names = request.httprequest.form.getlist('product_name[]')
            product_ids = request.httprequest.form.getlist('product_id[]')
            product_descriptions = request.httprequest.form.getlist('product_description[]')
            product_quantities = request.httprequest.form.getlist('product_quantity[]')
            product_uoms = request.httprequest.form.getlist('product_uom[]')

            for i, product_name in enumerate(product_names):
                if not product_name.strip():
                    continue

                product_id = product_ids[i] if i < len(product_ids) and product_ids[i] else None
                description = product_descriptions[i] if i < len(product_descriptions) else product_name
                quantity = float(product_quantities[i]) if i < len(product_quantities) and product_quantities[i] else 1.0

                # Get UOM - either from existing product or form input
                if product_id:
                    # Get UOM from existing product
                    existing_product = request.env['product.product'].sudo().browse(int(product_id))
                    uom_id = existing_product.sudo().uom_id.id if existing_product.exists() and existing_product.sudo().uom_id else None
                else:
                    # Use form input or get default UOM
                    uom_id = int(product_uoms[i]) if i < len(product_uoms) and product_uoms[i] else None

                # Get default UOM if still None
                if not uom_id:
                    default_uom = request.env['uom.uom'].sudo().search([('name', '=', 'Units')], limit=1)
                    uom_id = default_uom.id if default_uom else 1

                if not product_id:
                    # Create new product
                    product_vals = {
                        'name': product_name.strip(),
                        'type': 'consu',
                        'categ_id': 1,
                        'uom_id': uom_id,
                        'uom_po_id': uom_id,
                    }
                    new_product = request.env['product.product'].sudo().create(product_vals)
                    product_id = new_product.id

                line_vals = {
                    'description': description.strip() if description else product_name.strip(),
                    'quantity': quantity,
                    'product_id': int(product_id),
                }
                product_lines.append((0, 0, line_vals))

            if product_lines:
                vals['product_line_ids'] = product_lines

            # Update the request
            approval_sudo.write(vals)

            # Handle file attachments if any
            if request.httprequest.files:
                for file_key, file in request.httprequest.files.items():
                    if file.filename:
                        attachment_vals = {
                            'name': file.filename,
                            'datas': base64.b64encode(file.read()),
                            'res_model': 'approval.request',
                            'res_id': approval_sudo.id,
                        }
                        request.env['ir.attachment'].sudo().create(attachment_vals)

            # Submit the request
            approval_sudo.action_confirm()

            return request.redirect(f'/my/approval/{approval_id}')

        # GET request - show edit form
        if approval_sudo.request_status == 'pending':
            approval_sudo.request_status = 'new'
        partners = request.env['res.partner'].sudo().search([
            ('is_company', '=', True)
        ], limit=100)

        values = {
            'category': category,
            'partners': partners,
            'approval': approval_sudo,
            'edit_mode': True,
            'page_name': 'approval',
        }

        return request.render("platinum_proj.portal_approval_new", values)

    @http.route(['/my/approval/new'], type='http', auth="user", website=True)
    def portal_approval_categories(self, **kw):
        """Show available approval categories"""
        categories = request.env['approval.category'].search([
            ('active', '=', True)
        ])

        values = {
            'categories': categories,
            'page_name': 'approval',
        }
        return request.render("platinum_proj.portal_approval_categories", values)

    @http.route(['/my/approval/new/<int:category_id>'],
                type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_approval_new(self, category_id, **post):
        """Create new approval request"""
        category = request.env['approval.category'].browse(category_id)
        if not category.exists():
            return request.redirect('/my/approval/new')

        if request.httprequest.method == 'POST':
            # Process form submission for new request
            vals = {
                'name': post.get('name'),
                'category_id': category_id,
                'reason': post.get('reason'),
                'request_owner_id': request.env.user.id,
            }

            # Handle stock requisition auto-location assignment
            if category.name == 'Stock Requisition':
                # Auto-assign employee's location as destination
                employee = request.env['hr.employee'].search([
                    '|',
                    ('user_id', '=', request.env.user.id),
                    ('work_email', '=', request.env.user.email)
                ], limit=1)

                if employee:
                    # Try to find or create a location for the employee
                    employee_location = request.env['stock.location'].sudo().search([
                        ('name', 'ilike', employee.name),
                        ('usage', '=', 'internal')
                    ], limit=1)

                    if not employee_location:
                        # Create a location for this employee under main stock
                        main_stock = request.env.ref('stock.stock_location_stock', False)
                        employee_location = request.env['stock.location'].sudo().create({
                            'name': f"{employee.name} - Workstation",
                            'usage': 'internal',
                            'company_id': request.env.company.id,
                            'location_id': main_stock.id if main_stock else 1,
                        })

                    vals['dest_location_id'] = employee_location.id

                # Source location will be determined based on product availability after processing product lines

            # Handle optional fields based on category configuration
            if category.has_date and post.get('date'):
                vals['date'] = fields.Datetime.from_string(post.get('date'))
            if category.has_period != 'no':
                if post.get('date_start'):
                    vals['date_start'] = fields.Datetime.from_string(post.get('date_start'))
                if post.get('date_end'):
                    vals['date_end'] = fields.Datetime.from_string(post.get('date_end'))
            if category.has_amount and post.get('amount'):
                vals['amount'] = float(post.get('amount', 0))
            if category.has_quantity and post.get('quantity'):
                vals['quantity'] = float(post.get('quantity', 0))
            if category.has_location and post.get('location'):
                vals['location'] = post.get('location')
            if category.has_reference and post.get('reference'):
                vals['reference'] = post.get('reference')
            if category.has_partner and post.get('partner_id'):
                vals['partner_id'] = int(post.get('partner_id'))

            # Handle vendor name for new vendor creation
            if category.has_partner and post.get('vendor_name') and not post.get('partner_id'):
                vendor_name = post.get('vendor_name').strip()
                vendor_email = post.get('vendor_email', '').strip()
                vendor_phone = post.get('vendor_phone', '').strip()

                if vendor_name:
                    # Try to find existing vendor first
                    existing_vendor = request.env['res.partner'].sudo().search([
                        ('name', '=ilike', vendor_name),
                        ('is_company', '=', True)
                    ], limit=1)

                    if existing_vendor:
                        vals['partner_id'] = existing_vendor.id
                    else:
                        # Create new vendor
                        vendor_vals = {
                            'name': vendor_name,
                            'is_company': True,
                            'supplier_rank': 1,
                            'customer_rank': 0,
                        }
                        if vendor_email:
                            vendor_vals['email'] = vendor_email
                        if vendor_phone:
                            vendor_vals['phone'] = vendor_phone

                        new_vendor = request.env['res.partner'].sudo().create(vendor_vals)
                        vals['partner_id'] = new_vendor.id

            # Handle product lines if any (equipment/items)
            # Get form data using request.httprequest to access form arrays
            product_names = request.httprequest.form.getlist('product_name[]')
            product_ids = request.httprequest.form.getlist('product_id[]')
            product_descriptions = request.httprequest.form.getlist('product_description[]')
            product_quantities = request.httprequest.form.getlist('product_quantity[]')
            product_prices = request.httprequest.form.getlist('product_price[]')
            product_vendor_ids = request.httprequest.form.getlist('product_vendor_id[]')
            product_uoms = request.httprequest.form.getlist('product_uom[]')

            # Debug logging
            _logger.info(f"Product vendor IDs submitted: {product_vendor_ids}")
            _logger.info(f"Product prices submitted: {product_prices}")

            if product_names:
                product_lines = []
                for i, product_name in enumerate(product_names):
                    if product_name and product_name.strip():
                        # Get corresponding values for this line
                        product_id = product_ids[i] if i < len(product_ids) and product_ids[i] else None
                        description = product_descriptions[i] if i < len(product_descriptions) else product_name
                        quantity = float(product_quantities[i]) if i < len(product_quantities) and product_quantities[i] else 1.0
                        price = float(product_prices[i]) if i < len(product_prices) and product_prices[i] else 0.0
                        vendor_id = int(product_vendor_ids[i]) if i < len(product_vendor_ids) and product_vendor_ids[i] else None

                        # Get UOM - either from existing product or form input
                        if product_id:
                            # Get UOM from existing product
                            existing_product = request.env['product.product'].sudo().browse(int(product_id))
                            uom_id = existing_product.sudo().uom_id.id if existing_product.exists() and existing_product.sudo().uom_id else None
                        else:
                            # Use form input or get default UOM
                            uom_id = int(product_uoms[i]) if i < len(product_uoms) and product_uoms[i] else None

                        # Get default UOM if still None
                        if not uom_id:
                            default_uom = request.env['uom.uom'].sudo().search([('name', '=', 'Units')], limit=1)
                            uom_id = default_uom.id if default_uom else 1

                        # Create new product if no product_id provided
                        if not product_id:
                            product_vals = {
                                'name': product_name.strip(),
                                'type': 'consu',  # Consumable product type
                                'categ_id': 1,  # Default product category
                                'uom_id': uom_id,
                                'uom_po_id': uom_id,
                                'sale_ok': False,
                                'purchase_ok': True,
                                'is_storable': True,
                            }
                            # Note: Portal users still need sudo for product creation
                            new_product = request.env['product.product'].sudo().create(product_vals)
                            product_id = new_product.id

                        # Create product line
                        line_vals = {
                            'description': description.strip() if description else product_name.strip(),
                            'quantity': quantity,
                            'product_id': int(product_id),
                        }

                        # Add procurement-specific fields for purchase-type categories
                        if category.approval_type == 'purchase':
                            _logger.info(f"Processing purchase-type line {i}: price={price}, vendor_id={vendor_id}")
                            if price > 0:
                                line_vals['price_unit'] = price
                            if vendor_id:
                                line_vals['vendor_id'] = vendor_id

                                # Also create/find supplier info for RFQ creation
                                # The approvals_purchase addon expects seller_id to be set
                                product_template_id = new_product.product_tmpl_id.id if not product_id else \
                                                    request.env['product.product'].sudo().browse(int(product_id)).product_tmpl_id.id

                                supplier_info = request.env['product.supplierinfo'].sudo().search([
                                    ('partner_id', '=', vendor_id),
                                    ('product_tmpl_id', '=', product_template_id)
                                ], limit=1)

                                if not supplier_info:
                                    # Create supplier info for this vendor-product combination
                                    supplier_info = request.env['product.supplierinfo'].sudo().create({
                                        'partner_id': vendor_id,
                                        'product_tmpl_id': product_template_id,
                                        'min_qty': 1.0,
                                        'price': price if price > 0 else 0.0,
                                        'currency_id': request.env.company.currency_id.id,
                                        'company_id': request.env.company.id,
                                    })

                                line_vals['seller_id'] = supplier_info.id

                        product_lines.append((0, 0, line_vals))

                if product_lines:
                    vals['product_line_ids'] = product_lines

                    # For stock requisitions, auto-assign source location based on product availability
                    if category.name == 'Stock Requisition':
                        source_location = self._find_best_source_location(product_lines)
                        if source_location:
                            vals['source_location_id'] = source_location.id

            # Create new request (use sudo for sequence access)
            approval = request.env['approval.request'].sudo().create(vals)

            # Handle file attachments if any
            if request.httprequest.files:
                for file_key, file in request.httprequest.files.items():
                    if file.filename:
                        # Determine if this is a quotation based on field name or file type
                        is_quotation = (
                            'quotation' in file_key.lower() or
                            'quote' in file.filename.lower() or
                            file.filename.lower().endswith(('.pdf', '.doc', '.docx'))
                        )

                        attachment_vals = {
                            'name': file.filename,
                            'datas': base64.b64encode(file.read()),
                            'res_model': 'approval.request',
                            'res_id': approval.id,
                            'description': 'Quotation' if is_quotation else 'Supporting Document',
                        }

                        # Add quotation-specific metadata if available
                        if is_quotation and vals.get('partner_id'):
                            attachment_vals['res_field'] = f'quotation_vendor_{vals["partner_id"]}'

                        request.env['ir.attachment'].sudo().create(attachment_vals)

            # Submit the request (always confirm for portal submissions)
            # Portal users create requests that go directly into the approval workflow
            approval.sudo().action_confirm()

            return request.redirect(f'/my/approval/{approval.id}')

        # GET request - show form
        partners = request.env['res.partner'].search([]) if category.has_partner else []

        values = {
            'category': category,
            'partners': partners,
            'page_name': 'approval',
        }
        return request.render("platinum_proj.portal_approval_new", values)

    def _document_check_access(self, model_name, document_id, access_token=None):
        """Check access rights for portal documents"""
        document = request.env[model_name].browse([document_id])
        document_sudo = document.sudo()

        try:
            document.check_access('read')
        except AccessError:
            # Check if user owns this request
            if hasattr(document_sudo, 'request_owner_id'):
                if document_sudo.request_owner_id.id == request.env.user.id:
                    return document_sudo
            raise

        return document_sudo

    @http.route(['/my/approval/search_products'], type='json', auth="user", website=True)
    def portal_search_products(self, search='', limit=10, **kw):
        """Search products for approval requests"""
        if not search or len(search) < 2:
            return {'products': []}

        domain = [
            '|', '|',
            ('name', 'ilike', search),
            ('default_code', 'ilike', search),
            ('barcode', 'ilike', search)
        ]

        # Use sudo() until security rules take effect after module upgrade
        products = request.env['product.product'].sudo().search(domain, limit=limit)

        product_list = []
        for product in products:
            # Use sudo() for UOM access until security rules take effect
            uom_name = product.sudo().uom_id.name if product.sudo().uom_id else 'Units'
            uom_id = product.sudo().uom_id.id if product.sudo().uom_id else 1

            product_list.append({
                'id': product.id,
                'name': product.name,
                'default_code': product.default_code,
                'uom_name': uom_name,
                'uom_id': uom_id,
            })

        return {'products': product_list}

    @http.route(['/my/approval/get_product_info'], type='json', auth="user", website=True)
    def portal_get_product_info(self, product_id, **kw):
        """Get detailed product information"""
        # Use sudo() until security rules take effect after module upgrade
        product = request.env['product.product'].sudo().browse(int(product_id))
        if not product.exists():
            return {}

        # Use sudo() for UOM access until security rules take effect
        uom_name = product.sudo().uom_id.name if product.sudo().uom_id else 'Units'
        uom_id = product.sudo().uom_id.id if product.sudo().uom_id else 1

        return {
            'id': product.id,
            'name': product.name,
            'description': product.description_sale or product.name,
            'default_code': product.default_code,
            'uom_name': uom_name,
            'uom_id': uom_id,
            'categ_id': product.categ_id.id,
            'list_price': product.list_price,
        }

    @http.route(['/my/approval/search_vendors'], type='json', auth="user", website=True)
    def portal_search_vendors(self, search='', limit=10, **kw):
        """Search vendors for approval requests"""
        if not search or len(search) < 2:
            return {'vendors': []}

        domain = [
            ('is_company', '=', True),
            ('supplier_rank', '>', 0),
            '|', '|',
            ('name', 'ilike', search),
            ('email', 'ilike', search),
            ('vat', 'ilike', search)
        ]

        # Use sudo() since portal users don't have direct partner access
        vendors = request.env['res.partner'].sudo().search(domain, limit=limit)

        vendor_list = []
        for vendor in vendors:
            vendor_list.append({
                'id': vendor.id,
                'name': vendor.name,
                'email': vendor.email or '',
                'phone': vendor.phone or '',
                'vat': vendor.vat or '',
                'city': vendor.city or '',
                'country': vendor.country_id.name if vendor.country_id else '',
            })

        return {'vendors': vendor_list}

    @http.route(['/my/approval/create_vendor'], type='json', auth="user", website=True)
    def portal_create_vendor(self, name, email='', phone='', **kw):
        """Create new vendor from portal"""
        if not name or len(name.strip()) < 2:
            return {'success': False, 'message': 'Vendor name is required'}

        try:
            # Check if vendor already exists
            existing_vendor = request.env['res.partner'].sudo().search([
                ('name', '=ilike', name.strip()),
                ('is_company', '=', True)
            ], limit=1)

            if existing_vendor:
                return {
                    'success': True,
                    'vendor': {
                        'id': existing_vendor.id,
                        'name': existing_vendor.name,
                        'email': existing_vendor.email or '',
                        'phone': existing_vendor.phone or '',
                        'existing': True
                    }
                }

            # Create new vendor
            vendor_vals = {
                'name': name.strip(),
                'is_company': True,
                'supplier_rank': 1,
                'customer_rank': 0,
            }

            if email and email.strip():
                vendor_vals['email'] = email.strip()
            if phone and phone.strip():
                vendor_vals['phone'] = phone.strip()

            new_vendor = request.env['res.partner'].sudo().create(vendor_vals)

            return {
                'success': True,
                'vendor': {
                    'id': new_vendor.id,
                    'name': new_vendor.name,
                    'email': new_vendor.email or '',
                    'phone': new_vendor.phone or '',
                    'existing': False
                }
            }

        except Exception as e:
            _logger.error(f"Error creating vendor: {e}")
            return {'success': False, 'message': 'Error creating vendor. Please try again.'}

    @http.route(['/my/approval/check_stock_availability'], type='json', auth="user", website=True)
    def portal_check_stock_availability(self, product_id, quantity=1, **kw):
        """Check stock availability for a product across all locations"""
        if not product_id:
            return {'available': False, 'locations': []}

        product = request.env['product.product'].sudo().browse(int(product_id))
        if not product.exists():
            return {'available': False, 'locations': []}

        # Get all internal locations
        locations = request.env['stock.location'].sudo().search([
            ('usage', '=', 'internal'),
            ('company_id', '=', request.env.company.id)
        ])

        location_availability = []
        total_available = 0

        for location in locations:
            available_qty = request.env['stock.quant'].sudo()._get_available_quantity(
                product,
                location,
                strict=True
            )

            if available_qty > 0:
                location_availability.append({
                    'location_id': location.id,
                    'location_name': location.complete_name,
                    'available_qty': available_qty,
                    'sufficient': available_qty >= float(quantity)
                })
                total_available += available_qty

        return {
            'available': total_available >= float(quantity),
            'total_available': total_available,
            'locations': location_availability,
            'product_name': product.name
        }

    def _find_best_source_location(self, product_lines):
        """Find the best source location based on product availability"""
        # Get all internal locations
        locations = request.env['stock.location'].sudo().search([
            ('usage', '=', 'internal'),
            ('company_id', '=', request.env.company.id)
        ])

        location_scores = {}

        for location in locations:
            score = 0
            total_products = 0

            # Check availability of each product in this location
            for line_data in product_lines:
                # Extract product_id from the line data tuple (0, 0, {dict})
                if len(line_data) >= 3 and isinstance(line_data[2], dict):
                    product_id = line_data[2].get('product_id')
                    quantity = line_data[2].get('quantity', 1)

                    if product_id:
                        total_products += 1
                        available_qty = request.env['stock.quant'].sudo()._get_available_quantity(
                            request.env['product.product'].browse(product_id),
                            location,
                            strict=True
                        )

                        if available_qty >= quantity:
                            score += 1  # Full availability
                        elif available_qty > 0:
                            score += 0.5  # Partial availability

            if total_products > 0:
                location_scores[location] = score / total_products

        # Return location with highest availability score
        if location_scores:
            best_location = max(location_scores, key=location_scores.get)
            return best_location if location_scores[best_location] > 0 else None

        # Fallback to main stock location if no products or no availability found
        return request.env.ref('stock.stock_location_stock', False)