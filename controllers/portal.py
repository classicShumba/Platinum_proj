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

        # Always add approval count for portal users
        try:
            approval_count = request.env['approval.request'].search_count([
                ('request_owner_id', '=', request.env.user.id)
            ])
            values['approval_count'] = approval_count
        except:
            values['approval_count'] = 0

        return values

    def _get_approval_domain(self):
        """Get domain for user's approval requests"""
        return [('request_owner_id', '=', request.env.user.id)]

    @http.route(['/my/approvals', '/my/approvals/page/<int:page>'],
                type='http', auth="user", website=True)
    def portal_my_approvals(self, page=1, date_begin=None, date_end=None,
                           sortby=None, search=None, search_in='content',
                           groupby='none', filterby='all', **kw):
        """Employee portal page for approval requests"""
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
                uom_id = int(product_uoms[i]) if i < len(product_uoms) and product_uoms[i] else 1

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

            # Handle product lines if any (equipment/items)
            # Get form data using request.httprequest to access form arrays
            product_names = request.httprequest.form.getlist('product_name[]')
            product_ids = request.httprequest.form.getlist('product_id[]')
            product_descriptions = request.httprequest.form.getlist('product_description[]')
            product_quantities = request.httprequest.form.getlist('product_quantity[]')
            product_uoms = request.httprequest.form.getlist('product_uom[]')

            if product_names:
                product_lines = []
                for i, product_name in enumerate(product_names):
                    if product_name and product_name.strip():
                        # Get corresponding values for this line
                        product_id = product_ids[i] if i < len(product_ids) and product_ids[i] else None
                        description = product_descriptions[i] if i < len(product_descriptions) else product_name
                        quantity = float(product_quantities[i]) if i < len(product_quantities) and product_quantities[i] else 1.0
                        uom_id = int(product_uoms[i]) if i < len(product_uoms) and product_uoms[i] else 1

                        # Create new product if no product_id provided
                        if not product_id:
                            product_vals = {
                                'name': product_name.strip(),
                                'type': 'consu',  # Consumable product type
                                'categ_id': 1,  # Default product category
                                'uom_id': uom_id,
                                'uom_po_id': uom_id,
                            }
                            # Use sudo() since portal users don't have direct product creation access
                            new_product = request.env['product.product'].sudo().create(product_vals)
                            product_id = new_product.id

                        # Create product line
                        line_vals = {
                            'description': description.strip() if description else product_name.strip(),
                            'quantity': quantity,
                            'product_id': int(product_id),
                        }

                        product_lines.append((0, 0, line_vals))

                if product_lines:
                    vals['product_line_ids'] = product_lines

            # Create new request (use sudo for sequence access)
            approval = request.env['approval.request'].sudo().create(vals)

            # Handle file attachments if any
            if request.httprequest.files:
                for file_key, file in request.httprequest.files.items():
                    if file.filename:
                        attachment_vals = {
                            'name': file.filename,
                            'datas': base64.b64encode(file.read()),
                            'res_model': 'approval.request',
                            'res_id': approval.id,
                        }
                        request.env['ir.attachment'].sudo().create(attachment_vals)

            # Submit the request (always confirm for portal submissions)
            # Portal users create requests that go directly into the approval workflow
            approval.action_confirm()

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

        # Use sudo() since portal users don't have direct product access
        products = request.env['product.product'].sudo().search(domain, limit=limit)

        product_list = []
        for product in products:
            product_list.append({
                'id': product.id,
                'name': product.name,
                'default_code': product.default_code,
                'uom_name': product.uom_id.name,
                'uom_id': product.uom_id.id,
            })

        return {'products': product_list}

    @http.route(['/my/approval/get_product_info'], type='json', auth="user", website=True)
    def portal_get_product_info(self, product_id, **kw):
        """Get detailed product information"""
        # Use sudo() since portal users don't have direct product access
        product = request.env['product.product'].sudo().browse(int(product_id))
        if not product.exists():
            return {}

        return {
            'id': product.id,
            'name': product.name,
            'description': product.description_sale or product.name,
            'default_code': product.default_code,
            'uom_name': product.uom_id.name,
            'uom_id': product.uom_id.id,
            'categ_id': product.categ_id.id,
            'list_price': product.list_price,
        }