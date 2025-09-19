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

        if (!description) {
            alert('Please enter a description');
            return;
        }

        // Add item to list
        const item = {
            id: this.selectedProduct.id,
            name: this.selectedProduct.name,
            description: description,
            quantity: quantity,
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

        let html = '<div class="card"><div class="card-body"><h6 class="card-title">Items to Request:</h6>';

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