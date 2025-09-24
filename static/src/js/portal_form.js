/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * Portal form enhancements for approval requests
 */
publicWidget.registry.approvalPortalForm = publicWidget.Widget.extend({
    selector: '.o_approval_portal_form',
    events: {
        'change select[name="category_id"]': '_onCategoryChange',
        'change input[name="amount"]': '_onAmountChange',
        'click .o_approval_submit': '_onSubmitClick',
    },

    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        this._setupForm();
        return def;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Setup form initial state
     * @private
     */
    _setupForm: function () {
        this.$categorySelect = this.$('select[name="category_id"]');
        this.$amountInput = this.$('input[name="amount"]');
        this.$budgetInfo = this.$('.o_budget_info');

        // Initialize category change if a category is pre-selected
        if (this.$categorySelect.val()) {
            this._onCategoryChange();
        }
    },

    /**
     * Validate budget availability
     * @private
     * @param {float} amount
     * @param {int} categoryId
     */
    _validateBudget: function (amount, categoryId) {
        if (!amount || !categoryId) {
            return Promise.resolve(true);
        }

        return rpc('/my/approval/check_budget', {
            amount: parseFloat(amount),
            category_id: parseInt(categoryId),
        }).then((result) => {
            return result.available;
        });
    },

    /**
     * Update budget display
     * @private
     * @param {Object} budgetData
     */
    _updateBudgetDisplay: function (budgetData) {
        if (this.$budgetInfo.length && budgetData) {
            const available = budgetData.available_budget || 0;
            const spent = budgetData.spent_amount || 0;
            const total = budgetData.total_budget || 0;

            this.$budgetInfo.html(`
                <div class="alert alert-info">
                    <strong>Budget Status:</strong><br/>
                    Available: $${available.toFixed(2)}<br/>
                    Spent this month: $${spent.toFixed(2)}<br/>
                    Total budget: $${total.toFixed(2)}
                </div>
            `);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handle category change
     * @private
     */
    _onCategoryChange: function () {
        const categoryId = this.$categorySelect.val();
        if (categoryId) {
            // Fetch budget information for the selected category
            rpc('/my/approval/category_info', {
                category_id: parseInt(categoryId),
            }).then((result) => {
                this._updateBudgetDisplay(result.budget_info);

                // Show/hide fields based on category configuration
                this._toggleFieldVisibility(result.category_config);
            });
        }
    },

    /**
     * Handle amount change for budget validation
     * @private
     */
    _onAmountChange: function () {
        const amount = this.$amountInput.val();
        const categoryId = this.$categorySelect.val();

        if (amount && categoryId) {
            this._validateBudget(amount, categoryId).then((available) => {
                if (!available) {
                    this.$amountInput.addClass('is-invalid');
                    this._showBudgetError();
                } else {
                    this.$amountInput.removeClass('is-invalid');
                    this._hideBudgetError();
                }
            });
        }
    },

    /**
     * Handle form submission
     * @private
     * @param {Event} ev
     */
    _onSubmitClick: function (ev) {
        ev.preventDefault();

        // Check if products are required and validate
        const $productSection = this.$('#product_lines_section');
        const hasProductsRequired = $productSection.length > 0;

        if (hasProductsRequired) {
            const $hiddenInputs = this.$('#hidden_inputs input[name="product_name[]"]');
            if ($hiddenInputs.length === 0) {
                this._showError('At least one product/item is required for this request type.');
                return;
            }
        }

        const amount = this.$amountInput.val();
        const categoryId = this.$categorySelect.val();

        if (amount && categoryId) {
            this._validateBudget(amount, categoryId).then((available) => {
                if (available) {
                    // Submit the form
                    this.$el.closest('form')[0].submit();
                } else {
                    this._showBudgetError();
                }
            });
        } else {
            // Submit without budget validation if no amount
            this.$el.closest('form')[0].submit();
        }
    },

    /**
     * Show budget validation error
     * @private
     */
    _showBudgetError: function () {
        if (!this.$('.o_budget_error').length) {
            this.$amountInput.after(`
                <div class="invalid-feedback o_budget_error">
                    Insufficient budget available for this category.
                </div>
            `);
        }
    },

    /**
     * Hide budget validation error
     * @private
     */
    _hideBudgetError: function () {
        this.$('.o_budget_error').remove();
    },

    /**
     * Show general validation error
     * @private
     * @param {string} message
     */
    _showError: function (message) {
        // Remove any existing error messages
        this.$('.o_validation_error').remove();

        // Add error message at the top of the form
        this.$('.card-body').first().prepend(`
            <div class="alert alert-danger o_validation_error">
                <i class="fa fa-exclamation-triangle"></i> ${message}
            </div>
        `);

        // Scroll to top to show the error
        $('html, body').animate({
            scrollTop: this.$('.o_validation_error').offset().top - 20
        }, 500);
    },

    /**
     * Toggle field visibility based on category configuration
     * @private
     * @param {Object} config
     */
    _toggleFieldVisibility: function (config) {
        // Show/hide fields based on category requirements
        this.$('.o_field_date').toggleClass('d-none', !config.has_date);
        this.$('.o_field_amount').toggleClass('d-none', !config.has_amount);
        this.$('.o_field_quantity').toggleClass('d-none', !config.has_quantity);
        this.$('.o_field_location').toggleClass('d-none', !config.has_location);
        this.$('.o_field_reference').toggleClass('d-none', !config.has_reference);
        this.$('.o_field_partner').toggleClass('d-none', !config.has_partner);
    },
});

/**
 * Simplified Product Lines Manager
 */
publicWidget.registry.productLinesManager = publicWidget.Widget.extend({
    selector: '#product_lines_section',
    events: {
        'input #product_search_input': '_onProductSearch',
        'click .product-suggestion': '_onProductSelect',
        'click #add_item_btn': '_onAddItem',
        'click #cancel_item_btn': '_onCancelItem',
        'click .remove-item': '_onRemoveItem',
        'focus #product_search_input': '_onSearchFocus',
        'blur #product_search_input': '_onSearchBlur',
        'input #product_vendor_search': '_onProductVendorSearch',
        'click .vendor-suggestion': '_onProductVendorSelect',
        'click #clear_product_vendor_btn': '_onClearProductVendor',
        'focus #product_vendor_search': '_onProductVendorFocus',
        'blur #product_vendor_search': '_onProductVendorBlur',
    },

    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        this.items = [];
        this.searchTimeout = null;
        this.selectedProduct = null;

        // Pre-populate existing products in edit mode
        this._loadExistingProducts();

        return def;
    },

    /**
     * Load existing products in edit mode
     * @private
     */
    _loadExistingProducts: function () {
        const $existingData = this.$('#existing_products');
        if ($existingData.length) {
            try {
                const existingProducts = JSON.parse($existingData.text());
                this.items = existingProducts;
                this._updateItemsList();
                this._updateHiddenInputs();
            } catch (e) {
                console.error('Error loading existing products:', e);
            }
        }
    },

    /**
     * Handle product search input
     * @private
     */
    _onProductSearch: function (ev) {
        const searchTerm = ev.target.value.trim();

        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        if (searchTerm.length < 2) {
            this.$('#product_suggestions').hide();
            return;
        }

        // Debounce search
        this.searchTimeout = setTimeout(() => {
            this._performProductSearch(searchTerm);
        }, 300);
    },

    /**
     * Perform product search via RPC
     * @private
     */
    _performProductSearch: function (searchTerm) {
        rpc('/my/approval/search_products', {
            search: searchTerm,
            limit: 8
        }).then((result) => {
            this._renderSearchResults(result.products, searchTerm);
        }).catch(() => {
            this.$('#product_suggestions').hide();
        });
    },

    /**
     * Render search results
     * @private
     */
    _renderSearchResults: function (products, searchTerm) {
        const $suggestions = this.$('#product_suggestions');
        $suggestions.empty();

        if (products && products.length > 0) {
            products.forEach(product => {
                const $item = $(`
                    <div class="product-suggestion p-2 border-bottom" style="cursor: pointer;"
                         data-product-id="${product.id}"
                         data-product-name="${product.name}"
                         data-uom-id="${product.uom_id}">
                        <div class="d-flex justify-content-between">
                            <div>
                                <strong>${product.name}</strong>
                                ${product.default_code ? `<br><small class="text-muted">${product.default_code}</small>` : ''}
                            </div>
                            <small class="text-muted">${product.uom_name}</small>
                        </div>
                    </div>
                `);
                $suggestions.append($item);
            });
        }

        // Add "Create new product" option
        const $createItem = $(`
            <div class="product-suggestion p-2 text-primary bg-light" style="cursor: pointer;"
                 data-create-product="${searchTerm}">
                <i class="fa fa-plus me-1"></i> Create: "${searchTerm}"
            </div>
        `);
        $suggestions.append($createItem);

        $suggestions.show();
    },

    /**
     * Handle product selection
     * @private
     */
    _onProductSelect: function (ev) {
        const $item = $(ev.currentTarget);

        if ($item.data('create-product')) {
            // Create new product
            this.selectedProduct = {
                id: null,
                name: $item.data('create-product'),
                description: $item.data('create-product'),
                uom_id: 1,
                is_new: true
            };
        } else {
            // Select existing product
            this.selectedProduct = {
                id: $item.data('product-id'),
                name: $item.data('product-name'),
                description: $item.data('product-name'),
                uom_id: $item.data('uom-id'),
                is_new: false
            };
        }

        // Show add item form
        this._showAddItemForm();
        this.$('#product_suggestions').hide();
        this.$('#product_search_input').val('');
    },

    /**
     * Show add item form
     * @private
     */
    _showAddItemForm: function () {
        this.$('#selected_product_name').val(this.selectedProduct.name);
        this.$('#product_description').val(this.selectedProduct.description);
        this.$('#product_quantity').val(1);
        this.$('#add_item_form').show();
        this.$('#product_description').focus();
    },

    /**
     * Handle add item button
     * @private
     */
    _onAddItem: function () {
        const description = this.$('#product_description').val().trim();
        const quantity = parseFloat(this.$('#product_quantity').val()) || 1;
        const price = parseFloat(this.$('#product_price').val()) || 0;

        if (!description) {
            alert('Please enter a description');
            return;
        }

        // Get vendor info if selected
        const vendorId = this.$('#selected_product_vendor_id').val() || null;
        const vendorName = this.$('#selected_product_vendor_name').text() || '';

        // Check if this is a Stock Requisition and validate availability
        const categoryName = $('input[name="category_name"]').val() || '';
        if (categoryName === 'Stock Requisition' && this.selectedProduct.id && !this.selectedProduct.is_new) {
            this._checkStockAvailability(this.selectedProduct.id, quantity).then((result) => {
                if (!result.available) {
                    const message = `Insufficient stock for ${result.product_name}.\n` +
                                  `Requested: ${quantity}, Available: ${result.total_available}`;
                    if (confirm(message + '\n\nDo you want to proceed anyway?')) {
                        this._addItemToList(description, quantity, price, vendorId, vendorName);
                    }
                } else {
                    this._addItemToList(description, quantity, price, vendorId, vendorName);
                }
            }).catch(() => {
                // If check fails, proceed anyway
                this._addItemToList(description, quantity, price, vendorId, vendorName);
            });
        } else {
            this._addItemToList(description, quantity, price, vendorId, vendorName);
        }
    },

    /**
     * Add item to list (extracted for stock availability checking)
     * @private
     */
    _addItemToList: function(description, quantity, price, vendorId, vendorName) {
        const item = {
            id: this.selectedProduct.id,
            name: this.selectedProduct.name,
            description: description,
            quantity: quantity,
            price: price,
            vendor_id: vendorId,
            vendor_name: vendorName,
            uom_id: this.selectedProduct.uom_id,
            is_new: this.selectedProduct.is_new
        };

        this.items.push(item);
        this._updateItemsList();
        this._updateHiddenInputs();
        this._hideAddItemForm();
    },

    /**
     * Handle cancel item button
     * @private
     */
    _onCancelItem: function () {
        this._hideAddItemForm();
    },

    /**
     * Hide add item form
     * @private
     */
    _hideAddItemForm: function () {
        this.$('#add_item_form').hide();
        this.$('#product_price').val('');
        this.$('#selected_product_vendor_id').val('');
        this.$('#selected_product_vendor_display').hide();
        this.$('#product_vendor_search').show().val('');
        this.selectedProduct = null;
    },

    /**
     * Handle remove item
     * @private
     */
    _onRemoveItem: function (ev) {
        const index = $(ev.currentTarget).data('index');
        this.items.splice(index, 1);
        this._updateItemsList();
        this._updateHiddenInputs();
    },

    /**
     * Update items list display
     * @private
     */
    _updateItemsList: function () {
        const $itemsList = this.$('#items_list');
        const $noItemsMsg = this.$('#no_items_message');

        if (this.items.length === 0) {
            $noItemsMsg.show();
            $itemsList.empty();
            return;
        }

        $noItemsMsg.hide();

        // Check if this is purchase-type category (enhanced display)
        const isPurchaseType = document.querySelector('.o_approval_portal_form [name="category_id"]')?.value &&
                               document.querySelector('input[name="approval_type"]')?.value === 'purchase';

        let html = '<div class="card"><div class="card-body"><h6 class="card-title">Items to Request:</h6>';

        if (isPurchaseType) {
            // Enhanced display for procurement with vendor and price info
            html += '<div class="table-responsive"><table class="table table-sm">';
            html += '<thead><tr><th>Product</th><th>Qty</th><th>Price</th><th>Vendor</th><th>Total</th><th></th></tr></thead><tbody>';

            let grandTotal = 0;
            this.items.forEach((item, index) => {
                const subtotal = item.quantity * (item.price || 0);
                grandTotal += subtotal;

                html += `
                    <tr>
                        <td>
                            <strong>${item.name}</strong>
                            <br><small class="text-muted">${item.description}</small>
                        </td>
                        <td>${item.quantity}</td>
                        <td>${item.price ? '$' + item.price.toFixed(2) : '-'}</td>
                        <td>${item.vendor_name || '<em>Not specified</em>'}</td>
                        <td><strong>$${subtotal.toFixed(2)}</strong></td>
                        <td>
                            <button type="button" class="btn btn-sm btn-outline-danger remove-item" data-index="${index}">
                                <i class="fa fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });

            html += `</tbody><tfoot><tr><th colspan="4" class="text-end">Total:</th><th>$${grandTotal.toFixed(2)}</th><th></th></tr></tfoot></table></div>`;
        } else {
            // Simple display for other categories
            this.items.forEach((item, index) => {
                html += `
                    <div class="d-flex justify-content-between align-items-center border-bottom py-2">
                        <div class="flex-grow-1">
                            <strong>${item.name}</strong>
                            <br><small class="text-muted">${item.description}</small>
                        </div>
                        <div class="text-end me-3">
                            <span class="badge bg-primary">${item.quantity}</span>
                        </div>
                        <div>
                            <button type="button" class="btn btn-sm btn-outline-danger remove-item" data-index="${index}">
                                <i class="fa fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
        }

        html += '</div></div>';

        $itemsList.html(html);

        // Re-attach event handlers for dynamically created elements
        this._attachRemoveHandlers();
    },

    /**
     * Attach event handlers to remove buttons
     * @private
     */
    _attachRemoveHandlers: function () {
        const self = this;
        this.$('.remove-item').off('click').on('click', function(ev) {
            ev.preventDefault();
            const index = $(this).data('index');
            self.items.splice(index, 1);
            self._updateItemsList();
            self._updateHiddenInputs();
        });
    },

    /**
     * Update hidden form inputs
     * @private
     */
    _updateHiddenInputs: function () {
        const $hiddenInputs = this.$('#hidden_inputs');
        $hiddenInputs.empty();

        this.items.forEach((item, index) => {
            $hiddenInputs.append(`
                <input type="hidden" name="product_id[]" value="${item.id || ''}">
                <input type="hidden" name="product_name[]" value="${item.name}">
                <input type="hidden" name="product_description[]" value="${item.description}">
                <input type="hidden" name="product_quantity[]" value="${item.quantity}">
                <input type="hidden" name="product_price[]" value="${item.price || '0'}">
                <input type="hidden" name="product_vendor_id[]" value="${item.vendor_id || ''}">
                <input type="hidden" name="product_uom[]" value="${item.uom_id}">
            `);
        });
    },

    /**
     * Handle search focus
     * @private
     */
    _onSearchFocus: function () {
        // Could show recent searches or popular items
    },

    /**
     * Handle search blur
     * @private
     */
    _onSearchBlur: function () {
        // Delay hiding suggestions to allow clicks
        setTimeout(() => {
            this.$('#product_suggestions').hide();
        }, 200);
    },

    /**
     * Handle product vendor search
     * @private
     */
    _onProductVendorSearch: function (ev) {
        const searchTerm = ev.target.value.trim();

        if (this.productVendorTimeout) {
            clearTimeout(this.productVendorTimeout);
        }

        if (searchTerm.length < 2) {
            this.$('#product_vendor_suggestions').hide();
            return;
        }

        this.productVendorTimeout = setTimeout(() => {
            this._performProductVendorSearch(searchTerm);
        }, 300);
    },

    /**
     * Perform vendor search for product
     * @private
     */
    _performProductVendorSearch: function (searchTerm) {
        rpc('/my/approval/search_vendors', {
            search: searchTerm,
            limit: 5
        }).then((result) => {
            this._renderProductVendorResults(result.vendors);
        }).catch(() => {
            this.$('#product_vendor_suggestions').hide();
        });
    },

    /**
     * Render vendor search results for product
     * @private
     */
    _renderProductVendorResults: function (vendors) {
        const $suggestions = this.$('#product_vendor_suggestions');
        $suggestions.empty();

        if (vendors && vendors.length > 0) {
            vendors.forEach(vendor => {
                const details = [];
                if (vendor.email) details.push(vendor.email);
                if (vendor.city) details.push(vendor.city);

                const $item = $(`
                    <div class="vendor-suggestion p-2 border-bottom" style="cursor: pointer;"
                         data-vendor-id="${vendor.id}"
                         data-vendor-name="${vendor.name}"
                         data-vendor-email="${vendor.email}">
                        <div>
                            <strong>${vendor.name}</strong>
                            ${details.length > 0 ? `<br><small class="text-muted">${details.join(' • ')}</small>` : ''}
                        </div>
                    </div>
                `);
                $suggestions.append($item);
            });
        }

        $suggestions.show();
    },

    /**
     * Handle product vendor selection
     * @private
     */
    _onProductVendorSelect: function (ev) {
        const $item = $(ev.currentTarget);

        this.$('#selected_product_vendor_id').val($item.data('vendor-id'));
        this.$('#selected_product_vendor_name').text($item.data('vendor-name'));
        this.$('#selected_product_vendor_details').text($item.data('vendor-email') || '');

        this.$('#selected_product_vendor_display').show();
        this.$('#product_vendor_search').hide();
        this.$('#product_vendor_suggestions').hide();
    },

    /**
     * Clear product vendor selection
     * @private
     */
    _onClearProductVendor: function () {
        this.$('#selected_product_vendor_id').val('');
        this.$('#selected_product_vendor_display').hide();
        this.$('#product_vendor_search').show().val('');
    },

    /**
     * Handle product vendor search focus
     * @private
     */
    _onProductVendorFocus: function () {
        // Could show recent vendors
    },

    /**
     * Handle product vendor search blur
     * @private
     */
    _onProductVendorBlur: function () {
        setTimeout(() => {
            this.$('#product_vendor_suggestions').hide();
        }, 200);
    },

    /**
     * Check stock availability for a product
     * @private
     * @param {int} productId
     * @param {float} quantity
     * @returns {Promise}
     */
    _checkStockAvailability: function (productId, quantity) {
        return rpc('/my/approval/check_stock_availability', {
            product_id: productId,
            quantity: quantity || 1
        });
    },
});

/**
 * Vendor Search Manager for procurement requests
 */
publicWidget.registry.vendorSearchManager = publicWidget.Widget.extend({
    selector: '.o_field_partner',
    events: {
        'input #vendor_search': '_onVendorSearch',
        'click .vendor-suggestion': '_onVendorSelect',
        'click #clear_vendor_btn': '_onClearVendor',
        'click #create_vendor_btn': '_onCreateVendor',
        'click #cancel_vendor_btn': '_onCancelVendorForm',
        'focus #vendor_search': '_onSearchFocus',
        'blur #vendor_search': '_onSearchBlur',
    },

    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        this.searchTimeout = null;
        this.selectedVendor = null;
        return def;
    },

    /**
     * Handle vendor search input
     * @private
     */
    _onVendorSearch: function (ev) {
        const searchTerm = ev.target.value.trim();

        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        if (searchTerm.length < 2) {
            this.$('#vendor_suggestions').hide();
            return;
        }

        // Debounce search
        this.searchTimeout = setTimeout(() => {
            this._performVendorSearch(searchTerm);
        }, 300);
    },

    /**
     * Perform vendor search via RPC
     * @private
     */
    _performVendorSearch: function (searchTerm) {
        rpc('/my/approval/search_vendors', {
            search: searchTerm,
            limit: 8
        }).then((result) => {
            this._renderSearchResults(result.vendors, searchTerm);
        }).catch(() => {
            this.$('#vendor_suggestions').hide();
        });
    },

    /**
     * Render search results
     * @private
     */
    _renderSearchResults: function (vendors, searchTerm) {
        const $suggestions = this.$('#vendor_suggestions');
        $suggestions.empty();

        if (vendors && vendors.length > 0) {
            vendors.forEach(vendor => {
                const details = [];
                if (vendor.email) details.push(vendor.email);
                if (vendor.city) details.push(vendor.city);
                if (vendor.country) details.push(vendor.country);

                const $item = $(`
                    <div class="vendor-suggestion p-2 border-bottom" style="cursor: pointer;"
                         data-vendor-id="${vendor.id}"
                         data-vendor-name="${vendor.name}"
                         data-vendor-email="${vendor.email}"
                         data-vendor-phone="${vendor.phone}">
                        <div>
                            <strong>${vendor.name}</strong>
                            ${details.length > 0 ? `<br><small class="text-muted">${details.join(' • ')}</small>` : ''}
                        </div>
                    </div>
                `);
                $suggestions.append($item);
            });
        }

        // Add "Create new vendor" option
        const $createItem = $(`
            <div class="vendor-suggestion p-2 text-primary bg-light" style="cursor: pointer;"
                 data-create-vendor="${searchTerm}">
                <i class="fa fa-plus me-1"></i> Create new vendor: "${searchTerm}"
            </div>
        `);
        $suggestions.append($createItem);

        $suggestions.show();
    },

    /**
     * Handle vendor selection
     * @private
     */
    _onVendorSelect: function (ev) {
        const $item = $(ev.currentTarget);

        if ($item.data('create-vendor')) {
            // Show create vendor form
            this._showCreateVendorForm($item.data('create-vendor'));
        } else {
            // Select existing vendor
            this.selectedVendor = {
                id: $item.data('vendor-id'),
                name: $item.data('vendor-name'),
                email: $item.data('vendor-email'),
                phone: $item.data('vendor-phone'),
                existing: true
            };
            this._showSelectedVendor();
        }

        this.$('#vendor_suggestions').hide();
        this.$('#vendor_search').val('');
    },

    /**
     * Show selected vendor
     * @private
     */
    _showSelectedVendor: function () {
        const details = [];
        if (this.selectedVendor.email) details.push(this.selectedVendor.email);
        if (this.selectedVendor.phone) details.push(this.selectedVendor.phone);

        this.$('#selected_vendor_name').text(this.selectedVendor.name);
        this.$('#selected_vendor_details').text(details.join(' • '));
        this.$('#selected_vendor_display').show();
        this.$('#vendor_search').hide();

        // Update hidden fields
        this.$('#selected_partner_id').val(this.selectedVendor.id || '');
        this.$('#vendor_name_hidden').val(this.selectedVendor.name);
        this.$('#vendor_email_hidden').val(this.selectedVendor.email || '');
        this.$('#vendor_phone_hidden').val(this.selectedVendor.phone || '');
    },

    /**
     * Show create vendor form
     * @private
     */
    _showCreateVendorForm: function (vendorName) {
        this.$('#new_vendor_name').val(vendorName);
        this.$('#new_vendor_email').val('');
        this.$('#new_vendor_phone').val('');
        this.$('#new_vendor_form').show();
        this.$('#vendor_search').hide();
        this.$('#new_vendor_email').focus();
    },

    /**
     * Handle create vendor button
     * @private
     */
    _onCreateVendor: function () {
        const name = this.$('#new_vendor_name').val().trim();
        const email = this.$('#new_vendor_email').val().trim();
        const phone = this.$('#new_vendor_phone').val().trim();

        if (!name) {
            alert('Vendor name is required');
            return;
        }

        // Show loading state
        const $btn = this.$('#create_vendor_btn');
        const originalText = $btn.text();
        $btn.text('Creating...').prop('disabled', true);

        rpc('/my/approval/create_vendor', {
            name: name,
            email: email,
            phone: phone
        }).then((result) => {
            $btn.text(originalText).prop('disabled', false);

            if (result.success) {
                this.selectedVendor = result.vendor;
                this._showSelectedVendor();
                this.$('#new_vendor_form').hide();

                if (!result.vendor.existing) {
                    // Show success message for new vendor
                    this._showMessage('Vendor created successfully!', 'success');
                }
            } else {
                alert(result.message || 'Error creating vendor');
            }
        }).catch(() => {
            $btn.text(originalText).prop('disabled', false);
            alert('Error creating vendor. Please try again.');
        });
    },

    /**
     * Handle cancel vendor form
     * @private
     */
    _onCancelVendorForm: function () {
        this.$('#new_vendor_form').hide();
        this.$('#vendor_search').show().focus();
    },

    /**
     * Handle clear vendor
     * @private
     */
    _onClearVendor: function () {
        this.selectedVendor = null;
        this.$('#selected_vendor_display').hide();
        this.$('#vendor_search').show().val('').focus();

        // Clear hidden fields
        this.$('#selected_partner_id').val('');
        this.$('#vendor_name_hidden').val('');
        this.$('#vendor_email_hidden').val('');
        this.$('#vendor_phone_hidden').val('');
    },

    /**
     * Handle search focus
     * @private
     */
    _onSearchFocus: function () {
        // Could show recent vendors or popular vendors
    },

    /**
     * Handle search blur
     * @private
     */
    _onSearchBlur: function () {
        // Delay hiding suggestions to allow clicks
        setTimeout(() => {
            this.$('#vendor_suggestions').hide();
        }, 200);
    },

    /**
     * Show message to user
     * @private
     */
    _showMessage: function (message, type = 'info') {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-info';
        const $alert = $(`
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);

        this.$el.prepend($alert);

        // Auto-dismiss after 3 seconds
        setTimeout(() => {
            $alert.alert('close');
        }, 3000);
    },
});

/**
 * Approval request status widget for portal
 */
publicWidget.registry.approvalStatusWidget = publicWidget.Widget.extend({
    selector: '.o_approval_status_widget',

    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        this._setupStatusDisplay();
        return def;
    },

    /**
     * Setup status display with auto-refresh
     * @private
     */
    _setupStatusDisplay: function () {
        // Auto-refresh status every 30 seconds for pending requests
        if (this.$el.data('status') === 'pending') {
            setInterval(() => {
                this._refreshStatus();
            }, 30000);
        }
    },

    /**
     * Refresh approval status
     * @private
     */
    _refreshStatus: function () {
        const requestId = this.$el.data('request-id');
        if (requestId) {
            rpc('/my/approval/status', {
                request_id: parseInt(requestId),
            }).then((result) => {
                if (result.status !== this.$el.data('status')) {
                    // Reload page if status changed
                    window.location.reload();
                }
            });
        }
    },
});