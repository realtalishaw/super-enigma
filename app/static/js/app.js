// Custom JavaScript for Weave UI
// This file can be used for any custom JS beyond Alpine.js and HTMX

// Global utility functions
window.Weave = {
    // Show toast notification
    showToast: function(message, type = 'info') {
        const toastArea = document.getElementById('toast-area');
        if (!toastArea) return;
        
        const toast = document.createElement('div');
        const bgColor = type === 'error' ? 'bg-red-100 border-red-400 text-red-700' :
                       type === 'success' ? 'bg-green-100 border-green-400 text-green-700' :
                       type === 'warning' ? 'bg-yellow-100 border-yellow-400 text-yellow-700' :
                       'bg-blue-100 border-blue-400 text-blue-700';
        
        toast.className = `${bgColor} border px-4 py-3 rounded mb-4 max-w-sm`;
        toast.textContent = message;
        
        toastArea.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    },
    
    // Format date for display
    formatDate: function(dateString) {
        if (!dateString) return 'Unknown';
        try {
            const date = new Date(dateString);
            return date.toLocaleString();
        } catch (e) {
            return dateString;
        }
    },
    
    // Debounce function for search inputs
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Initialize any global event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Add any global initialization code here
    
    // Example: Add focus ring to all focusable elements
    const focusableElements = document.querySelectorAll('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])');
    focusableElements.forEach(el => {
        el.classList.add('focus-ring');
    });
});
