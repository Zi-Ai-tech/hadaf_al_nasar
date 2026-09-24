// ================================
// Hadaf Al Nasar - Main Application Script
// ================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('Hadaf Al Nasar - Application initialized');

    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // ================================
    // Dashboard Enhancements
    // ================================
    function initializeDashboard() {
        const statCards = document.querySelectorAll('.stat-card');
        if (statCards.length > 0) {
            // Animate stat cards on load
            statCards.forEach((card, index) => {
                card.style.animationDelay = `${index * 0.1}s`;
                card.classList.add('animate__animated', 'animate__fadeInUp');
            });

            // Add click effects to action cards
            const actionCards = document.querySelectorAll('.modern-list .list-group-item');
            actionCards.forEach(card => {
                card.addEventListener('click', function() {
                    this.style.transform = 'scale(0.98)';
                    setTimeout(() => {
                        this.style.transform = '';
                    }, 150);
                });
            });
        }
    }

    // ================================
    // Customer Page Script
    // ================================
    function initializeCustomerPage() {
        const editModal = document.getElementById('editCustomerModal');
        if (!editModal) return;

        const modal = new bootstrap.Modal(editModal);
        let currentEditId = null;

        // Get CSRF token from meta
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

        // -------------------
        // DELETE CUSTOMER
        // -------------------
        const customersTable = document.getElementById('customersTable');
        if (customersTable) {
            customersTable.addEventListener('click', function(e) {
                if(e.target.classList.contains('delete-customer')) {
                    const id = e.target.dataset.id;
                    if(confirm('Are you sure you want to delete this customer? This action cannot be undone.')) {
                        showLoading('Deleting customer...');
                        fetch(`/accounts/customers/${id}/delete`, {
                            method: 'POST',
                            headers: { 
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRFToken': csrfToken
                            }
                        })
                        .then(res => res.json())
                        .then(data => {
                            hideLoading();
                            if(data.success) {
                                const row = document.getElementById(`customer-${id}`);
                                if (row) {
                                    row.style.opacity = '0';
                                    setTimeout(() => {
                                        row.remove();
                                        showToast('Customer deleted successfully!', 'success');
                                    }, 300);
                                }
                            } else {
                                showToast(data.message || 'Error deleting customer', 'error');
                            }
                        })
                        .catch(err => {
                            hideLoading();
                            console.error('Delete error:', err);
                            showToast('Network error occurred', 'error');
                        });
                    }
                }
            });

            // -------------------
            // EDIT CUSTOMER (show modal)
            // -------------------
            customersTable.addEventListener('click', function(e) {
                if(e.target.classList.contains('edit-customer')) {
                    const id = e.target.dataset.id;
                    currentEditId = id;
                    showLoading('Loading customer data...');
                    fetch(`/accounts/customers/${id}`)
                    .then(res => res.json())
                    .then(data => {
                        hideLoading();
                        if(data.success) {
                            const c = data.customer;
                            // Populate form fields
                            document.getElementById('editCustomerId').value = c.id;
                            document.getElementById('editCompanyName').value = c.company_name || '';
                            document.getElementById('editEmail').value = c.email || '';
                            document.getElementById('editMobile').value = c.mobile || '';
                            document.getElementById('editPhone').value = c.phone || '';
                            document.getElementById('editTradeLicense').value = c.trade_license_number || '';
                            document.getElementById('editTRN').value = c.trn || '';
                            document.getElementById('editLegalForm').value = c.legal_form || '';
                            document.getElementById('editContactPerson').value = c.contact_person || '';
                            document.getElementById('editContactDesignation').value = c.contact_designation || '';
                            document.getElementById('editAddress').value = c.address || '';
                            document.getElementById('editEmirate').value = c.emirate || '';
                            document.getElementById('editCity').value = c.city || '';
                            document.getElementById('editPOBox').value = c.po_box || '';
                            document.getElementById('editBusinessActivities').value = c.business_activities || '';
                            document.getElementById('editIndustryType').value = c.industry_type || '';
                            document.getElementById('editCreditLimit').value = c.credit_limit || '';
                            document.getElementById('editPaymentTerms').value = c.payment_terms || '';
                            modal.show();
                        } else {
                            showToast(data.message || 'Error loading customer data', 'error');
                        }
                    })
                    .catch(err => {
                        hideLoading();
                        console.error('Edit fetch error:', err);
                        showToast('Network error occurred', 'error');
                    });
                }
            });
        }

        // -------------------
        // EDIT CUSTOMER (submit modal)
        // -------------------
        const editForm = document.getElementById('editCustomerForm');
        if (editForm) {
            editForm.addEventListener('submit', function(e) {
                e.preventDefault();
                showLoading('Updating customer...');
                const formData = new FormData(editForm);

                fetch(`/accounts/customers/${currentEditId}/update`, {
                    method: 'POST',
                    headers: { 
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    },
                    body: formData
                })
                .then(res => res.json())
                .then(data => {
                    hideLoading();
                    if(data.success) {
                        const c = data.customer;
                        const row = document.getElementById(`customer-${c.id}`);
                        if (row) {
                            row.innerHTML = `
                                <td>${c.id}</td>
                                <td>${c.company_name}</td>
                                <td>${c.email}</td>
                                <td>${c.mobile}</td>
                                <td>
                                    <button class="btn btn-sm btn-primary edit-customer" data-id="${c.id}">Edit</button>
                                    <button class="btn btn-sm btn-danger delete-customer" data-id="${c.id}">Delete</button>
                                </td>
                            `;
                        }
                        modal.hide();
                        showToast('Customer updated successfully!', 'success');
                    } else {
                        showToast(data.message || 'Error updating customer', 'error');
                    }
                })
                .catch(err => {
                    hideLoading();
                    console.error('Edit submit error:', err);
                    showToast('Network error occurred', 'error');
                });
            });
        }

        // -------------------
        // SEARCH FILTER
        // -------------------
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                const val = this.value.toLowerCase();
                const rows = document.querySelectorAll('#customersTable tbody tr');
                let visibleCount = 0;
                
                rows.forEach(tr => {
                    const matches = tr.textContent.toLowerCase().includes(val);
                    tr.style.display = matches ? '' : 'none';
                    if (matches) visibleCount++;
                });
                
                // Update results counter if it exists
                const resultsCounter = document.getElementById('resultsCounter');
                if (resultsCounter) {
                    resultsCounter.textContent = `Showing ${visibleCount} of ${rows.length} customers`;
                }
            });
        }
    }

    // ================================
    // Invoice Page Enhancements
    // ================================
    function initializeInvoicePage() {
        // Auto-calculate line totals
        const invoiceForm = document.querySelector('form[action*="invoice"]');
        if (invoiceForm) {
            invoiceForm.addEventListener('input', function(e) {
                if (e.target.classList.contains('item-quantity') || e.target.classList.contains('item-price')) {
                    const row = e.target.closest('.invoice-item-row');
                    if (row) {
                        const quantity = parseFloat(row.querySelector('.item-quantity').value) || 0;
                        const price = parseFloat(row.querySelector('.item-price').value) || 0;
                        const total = quantity * price;
                        const totalField = row.querySelector('.item-total');
                        if (totalField) {
                            totalField.textContent = total.toFixed(2);
                        }
                    }
                }
            });
        }
    }

    // ================================
    // Utility Functions
    // ================================
    function showLoading(message = 'Loading...') {
        // Remove existing loading overlay
        hideLoading();
        
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
        document.body.style.overflow = 'hidden';
    }

    function hideLoading() {
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.remove();
        }
        document.body.style.overflow = '';
    }

    function showToast(message, type = 'info') {
        // Remove existing toasts
        document.querySelectorAll('.toast-container').forEach(container => container.remove());
        
        const toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        document.body.appendChild(toastContainer);
        
        const bsToast = new bootstrap.Toast(toast, { delay: 4000 });
        bsToast.show();
        
        // Auto remove after hide
        toast.addEventListener('hidden.bs.toast', () => {
            toastContainer.remove();
        });
    }

    // ================================
    // Form Validation Enhancements
    // ================================
    function initializeFormValidation() {
        // Add real-time validation to all forms
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                const requiredFields = form.querySelectorAll('[required]');
                let valid = true;
                
                requiredFields.forEach(field => {
                    if (!field.value.trim()) {
                        field.classList.add('is-invalid');
                        valid = false;
                    } else {
                        field.classList.remove('is-invalid');
                    }
                });
                
                if (!valid) {
                    e.preventDefault();
                    showToast('Please fill in all required fields', 'error');
                }
            });
        });
    }

    // ================================
    // Initialize All Components
    // ================================
    initializeDashboard();
    initializeCustomerPage();
    initializeInvoicePage();
    initializeFormValidation();

    // ================================
    // Global Error Handler
    // ================================
    window.addEventListener('error', function(e) {
        console.error('Global error:', e.error);
    });

    // ================================
    // Network Status Monitor
    // ================================
    window.addEventListener('online', function() {
        showToast('Connection restored', 'success');
    });

    window.addEventListener('offline', function() {
        showToast('You are currently offline', 'warning');
    });
});

// ================================
// CSS for Dynamic Elements
// ================================
const dynamicStyles = `
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    backdrop-filter: blur(5px);
}

.loading-spinner {
    text-align: center;
    color: white;
}

.loading-spinner .spinner-border {
    width: 3rem;
    height: 3rem;
}

.toast-container {
    z-index: 9999;
}

.animate__animated {
    animation-duration: 0.6s;
}

.modern-list .list-group-item {
    transition: all 0.3s ease;
}

.modern-list .list-group-item:hover {
    transform: translateX(5px);
}

.stat-card {
    transition: all 0.3s ease;
}

.stat-card:hover {
    transform: translateY(-5px);
}
`;

// Inject dynamic styles
const styleSheet = document.createElement('style');
styleSheet.textContent = dynamicStyles;
document.head.appendChild(styleSheet);