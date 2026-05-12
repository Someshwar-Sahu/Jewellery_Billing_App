/**
 * JewelBill — ui.js
 * Phase 11: Additive UI-only JavaScript
 *
 * Rules:
 *  - Does NOT touch invoice.js or any existing business logic
 *  - Does NOT redefine any existing functions
 *  - Purely handles: sidebar, toasts, tooltips, ripple, mobile nav,
 *    table search, confirm dialogs, skeleton loaders, active nav detection
 */

(function () {
  'use strict';

  /* ═══════════════════════════════════════════════════
     1. SIDEBAR
  ═══════════════════════════════════════════════════ */

  const sidebar        = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('open');
    if (sidebarOverlay) sidebarOverlay.classList.add('active');
    document.body.classList.add('sidebar-open');
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('open');
    if (sidebarOverlay) sidebarOverlay.classList.remove('active');
    document.body.classList.remove('sidebar-open');
  }

  // Expose globally so inline onclick= in base.html works
  window.openSidebar  = openSidebar;
  window.closeSidebar = closeSidebar;

  // Close sidebar on Escape key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });

  // Desktop: sidebar is always visible — no collapse needed
  // Mobile: sidebar slides in over content
  // Sidebar collapse (desktop toggle) — optional compact mode
  const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener('click', function () {
      document.body.classList.toggle('sidebar-collapsed');
      const collapsed = document.body.classList.contains('sidebar-collapsed');
      localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
    });
  }

  // Restore desktop collapsed state
  if (window.innerWidth >= 1024) {
    if (localStorage.getItem('sidebarCollapsed') === '1') {
      document.body.classList.add('sidebar-collapsed');
    }
  }

  /* ═══════════════════════════════════════════════════
     2. ACTIVE NAV AUTO-DETECTION
     Falls back if Jinja blocks aren't set
  ═══════════════════════════════════════════════════ */

  (function markActiveNav() {
    const path = window.location.pathname;

    function markBestMatch(selector) {
      const items = Array.from(document.querySelectorAll(selector));
      if (!items.length) return;

      // Respect server-rendered active states from Jinja blocks.
      if (items.some(function (item) { return item.classList.contains('active'); })) return;

      let bestItem = null;
      let bestLen = -1;

      items.forEach(function (item) {
        const href = item.getAttribute('href');
        if (!href || href === '#') return;

        const exact = href === path;
        const prefix = href !== '/' && (path === href || path.startsWith(href + '/'));
        if (!exact && !prefix) return;

        if (href.length > bestLen) {
          bestLen = href.length;
          bestItem = item;
        }
      });

      if (bestItem) bestItem.classList.add('active');
    }

    markBestMatch('.nav-item');
    markBestMatch('.bottom-nav-item');
  })();

  /* ═══════════════════════════════════════════════════
     3. TOAST NOTIFICATION SYSTEM
  ═══════════════════════════════════════════════════ */

  /**
   * Show a toast notification.
   * @param {string} message  — Text to display
   * @param {'success'|'error'|'info'|'warning'} type
   * @param {number} duration — ms before auto-dismiss (0 = sticky)
   */
  function showToast(message, type, duration) {
    type     = type     || 'info';
    duration = duration !== undefined ? duration : 4000;

    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = {
      success : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
      error   : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      warning : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info    : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    };

    const toast = document.createElement('div');
    toast.className = 'toast toast--' + type;
    toast.innerHTML =
      '<span class="toast-icon"></span>' +
      '<span class="toast-msg"></span>' +
      '<button class="toast-close" aria-label="Dismiss">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
      '</button>';
    const iconEl = toast.querySelector('.toast-icon');
    const msgEl = toast.querySelector('.toast-msg');
    if (iconEl) iconEl.innerHTML = (icons[type] || icons.info);
    if (msgEl) msgEl.textContent = message == null ? '' : String(message);

    toast.querySelector('.toast-close').addEventListener('click', function () {
      dismissToast(toast);
    });

    container.appendChild(toast);

    // Trigger entrance animation
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        toast.classList.add('toast--visible');
      });
    });

    if (duration > 0) {
      setTimeout(function () { dismissToast(toast); }, duration);
    }

    return toast;
  }

  function dismissToast(toast) {
    if (!toast || toast._dismissing) return;
    toast._dismissing = true;
    toast.classList.remove('toast--visible');
    toast.classList.add('toast--out');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }

  // Expose globally — templates can call window.showToast(...)
  window.showToast = showToast;

  // Auto-show flash messages rendered by Jinja into a hidden element
  // Pattern: <div id="flashMessages" data-messages='[{"type":"success","text":"Saved"}]'></div>
  (function renderFlashMessages() {
    const el = document.getElementById('flashMessages');
    if (!el) return;
    try {
      const msgs = JSON.parse(el.getAttribute('data-messages') || '[]');
      msgs.forEach(function (m, i) {
        setTimeout(function () {
          showToast(m.text, m.type || 'info');
        }, i * 200);
      });
    } catch (_) {}
  })();

  /* ═══════════════════════════════════════════════════
     4. CONFIRM DIALOG (replaces browser confirm())
  ═══════════════════════════════════════════════════ */

  /**
   * Show a styled confirm dialog.
   * @param {object} opts
   *   title    {string}
   *   message  {string}
   *   confirm  {string}  button label
   *   cancel   {string}  button label
   *   danger   {boolean} red confirm button
   *   onConfirm {function}
   *   onCancel  {function}
   */
  function showConfirm(opts) {
    opts = opts || {};

    // Remove existing
    const existing = document.getElementById('confirmDialog');
    if (existing) existing.parentNode.removeChild(existing);

    const overlay = document.createElement('div');
    overlay.id        = 'confirmDialog';
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
      '<div class="confirm-box">' +
        '<div class="confirm-header">' +
          '<span class="confirm-title"></span>' +
        '</div>' +
        '<div class="confirm-body">' +
          '<p class="confirm-message"></p>' +
        '</div>' +
        '<div class="confirm-footer">' +
          '<button class="btn btn-ghost confirm-cancel-btn"></button>' +
          '<button class="btn ' + (opts.danger ? 'btn-danger' : 'btn-gold') + ' confirm-ok-btn"></button>' +
        '</div>' +
      '</div>';
    const titleEl = overlay.querySelector('.confirm-title');
    const msgEl = overlay.querySelector('.confirm-message');
    const cancelEl = overlay.querySelector('.confirm-cancel-btn');
    const okEl = overlay.querySelector('.confirm-ok-btn');
    if (titleEl) titleEl.textContent = opts.title || 'Confirm';
    if (msgEl) msgEl.textContent = opts.message || 'Are you sure?';
    if (cancelEl) cancelEl.textContent = opts.cancel || 'Cancel';
    if (okEl) okEl.textContent = opts.confirm || 'Confirm';

    document.body.appendChild(overlay);

    // Animate in
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        overlay.classList.add('confirm-overlay--visible');
      });
    });

    let settled = false;
    let keyHandler = null;
    function close() {
      if (settled) return;
      settled = true;
      if (keyHandler) {
        document.removeEventListener('keydown', keyHandler);
        keyHandler = null;
      }
      overlay.classList.remove('confirm-overlay--visible');
      setTimeout(function () {
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      }, 250);
    }

    overlay.querySelector('.confirm-cancel-btn').addEventListener('click', function () {
      close();
      if (typeof opts.onCancel === 'function') opts.onCancel();
    });

    overlay.querySelector('.confirm-ok-btn').addEventListener('click', function () {
      close();
      if (typeof opts.onConfirm === 'function') opts.onConfirm();
    });

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        close();
        if (typeof opts.onCancel === 'function') opts.onCancel();
      }
    });

    keyHandler = function (e) {
      if (e.key === 'Escape') {
        close();
        if (typeof opts.onCancel === 'function') opts.onCancel();
      }
      if (e.key === 'Enter') {
        close();
        if (typeof opts.onConfirm === 'function') opts.onConfirm();
      }
    };
    document.addEventListener('keydown', keyHandler);
  }

  window.showConfirm = showConfirm;

  /* ═══════════════════════════════════════════════════
     5. RIPPLE EFFECT on buttons
  ═══════════════════════════════════════════════════ */

  document.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn');
    if (!btn) return;

    const circle = document.createElement('span');
    circle.className = 'btn-ripple';

    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    circle.style.width  = size + 'px';
    circle.style.height = size + 'px';
    circle.style.left   = (e.clientX - rect.left - size / 2) + 'px';
    circle.style.top    = (e.clientY - rect.top  - size / 2) + 'px';

    btn.appendChild(circle);
    setTimeout(function () {
      if (circle.parentNode) circle.parentNode.removeChild(circle);
    }, 600);
  });

  /* ═══════════════════════════════════════════════════
     6. LIVE TABLE SEARCH
     Add data-search-target="tableId" to an input
     to filter that table's tbody rows by text content.
  ═══════════════════════════════════════════════════ */

  document.querySelectorAll('[data-search-target]').forEach(function (input) {
    input.addEventListener('input', function () {
      const tableId = input.getAttribute('data-search-target');
      const table   = document.getElementById(tableId);
      if (!table) return;

      const query = input.value.trim().toLowerCase();
      const rows  = table.querySelectorAll('tbody tr');
      let   visible = 0;

      rows.forEach(function (row) {
        const text = row.textContent.toLowerCase();
        const show = !query || text.includes(query);
        row.style.display = show ? '' : 'none';
        if (show) visible++;
      });

      // Show/hide empty state
      const emptyEl = document.getElementById(tableId + '_empty');
      if (emptyEl) {
        emptyEl.style.display = (visible === 0 && query) ? '' : 'none';
      }

      // Update count badge if present
      const countEl = document.getElementById(tableId + '_count');
      if (countEl) {
        countEl.textContent = visible;
      }
    });
  });

  /* ═══════════════════════════════════════════════════
     7. SORTABLE TABLE HEADERS
     Add data-sort to <th> elements to enable click-sort.
  ═══════════════════════════════════════════════════ */

  document.querySelectorAll('th[data-sort]').forEach(function (th) {
    th.style.cursor = 'pointer';
    th.setAttribute('title', 'Click to sort');

    th.addEventListener('click', function () {
      const table = th.closest('table');
      if (!table) return;

      const tbody   = table.querySelector('tbody');
      const colIdx  = Array.from(th.parentNode.children).indexOf(th);
      const asc     = th.dataset.sortDir !== 'asc';
      th.dataset.sortDir = asc ? 'asc' : 'desc';

      // Reset other headers
      table.querySelectorAll('th[data-sort]').forEach(function (other) {
        if (other !== th) {
          delete other.dataset.sortDir;
          other.classList.remove('sort-asc', 'sort-desc');
        }
      });
      th.classList.toggle('sort-asc', asc);
      th.classList.toggle('sort-desc', !asc);

      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function (a, b) {
        const aVal = (a.children[colIdx] || {}).textContent.trim();
        const bVal = (b.children[colIdx] || {}).textContent.trim();

        // Numeric sort if possible
        const aNum = parseFloat(aVal.replace(/[₹,]/g, ''));
        const bNum = parseFloat(bVal.replace(/[₹,]/g, ''));

        if (!isNaN(aNum) && !isNaN(bNum)) {
          return asc ? aNum - bNum : bNum - aNum;
        }
        return asc
          ? aVal.localeCompare(bVal, 'en', { sensitivity: 'base' })
          : bVal.localeCompare(aVal, 'en', { sensitivity: 'base' });
      });

      rows.forEach(function (row) { tbody.appendChild(row); });
    });
  });

  /* ═══════════════════════════════════════════════════
     8. TOOLTIP SYSTEM
     Add title="..." (native) or data-tip="..." for custom styled tooltips.
  ═══════════════════════════════════════════════════ */

  (function initTooltips() {
    let tip = null;

    function createTip(text) {
      const el    = document.createElement('div');
      el.className = 'ui-tooltip';
      el.textContent = text;
      document.body.appendChild(el);
      return el;
    }

    function removeTip() {
      if (tip) {
        tip.classList.remove('ui-tooltip--visible');
        const t = tip;
        tip = null;
        setTimeout(function () {
          if (t.parentNode) t.parentNode.removeChild(t);
        }, 200);
      }
    }

    document.addEventListener('mouseover', function (e) {
      const el   = e.target.closest('[data-tip]');
      if (!el) return;
      const text = el.getAttribute('data-tip');
      if (!text) return;

      tip = createTip(text);
      const rect = el.getBoundingClientRect();
      tip.style.left = (rect.left + rect.width / 2 + window.scrollX) + 'px';
      tip.style.top  = (rect.top  - 8 + window.scrollY) + 'px';

      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          if (tip) tip.classList.add('ui-tooltip--visible');
        });
      });
    });

    document.addEventListener('mouseout', function (e) {
      if (e.target.closest('[data-tip]')) removeTip();
    });
  })();

  /* ═══════════════════════════════════════════════════
     9. COPY TO CLIPBOARD
     Add data-copy="text" to any element.
  ═══════════════════════════════════════════════════ */

  document.addEventListener('click', function (e) {
    const el = e.target.closest('[data-copy]');
    if (!el) return;

    const text = el.getAttribute('data-copy');
    if (!text) return;

    navigator.clipboard.writeText(text).then(function () {
      showToast('Copied to clipboard', 'success', 2000);
    }).catch(function () {
      // Fallback for older browsers
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity  = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showToast('Copied!', 'success', 2000);
    });
  });

  /* ═══════════════════════════════════════════════════
     10. FORM DIRTY STATE WARNING
     Add data-dirty-guard to a <form> to warn before leaving
     if any field has been changed.
  ═══════════════════════════════════════════════════ */

  document.querySelectorAll('form[data-dirty-guard]').forEach(function (form) {
    let isDirty = false;
    let submitted = false;

    form.addEventListener('input',  function () { isDirty = true; });
    form.addEventListener('change', function () { isDirty = true; });
    form.addEventListener('submit', function () { submitted = true; });

    window.addEventListener('beforeunload', function (e) {
      if (isDirty && !submitted) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Leave anyway?';
      }
    });
  });

  /* ═══════════════════════════════════════════════════
     11. SKELETON LOADER HELPER
     Call showSkeleton(containerId) / hideSkeleton(containerId)
     to show loading placeholders while data loads.
  ═══════════════════════════════════════════════════ */

  function showSkeleton(containerId, rows) {
    rows = rows || 5;
    const container = document.getElementById(containerId);
    if (!container) return;
    container.dataset.originalHtml = container.innerHTML;

    let html = '<div class="skeleton-rows">';
    for (let i = 0; i < rows; i++) {
      html += '<div class="skeleton-row">' +
        '<div class="skeleton skeleton-sm"></div>' +
        '<div class="skeleton skeleton-md"></div>' +
        '<div class="skeleton skeleton-sm"></div>' +
        '<div class="skeleton skeleton-lg"></div>' +
      '</div>';
    }
    html += '</div>';
    container.innerHTML = html;
  }

  function hideSkeleton(containerId) {
    const container = document.getElementById(containerId);
    if (!container || !container.dataset.originalHtml) return;
    container.innerHTML = container.dataset.originalHtml;
    delete container.dataset.originalHtml;
  }

  window.showSkeleton = showSkeleton;
  window.hideSkeleton = hideSkeleton;

  /* ═══════════════════════════════════════════════════
     12. NUMBER FORMATTING HELPERS
     Available globally for templates that need them.
  ═══════════════════════════════════════════════════ */

  /**
   * Format a number as Indian currency string: ₹1,23,456.78
   */
  function formatINR(amount) {
    const num = parseFloat(amount);
    if (isNaN(num)) return '—';
    return '₹' + num.toLocaleString('en-IN', {
      minimumFractionDigits : 2,
      maximumFractionDigits : 2,
    });
  }

  /**
   * Format a number with Indian grouping (no ₹)
   */
  function formatNum(amount, decimals) {
    const num = parseFloat(amount);
    if (isNaN(num)) return '—';
    return num.toLocaleString('en-IN', {
      minimumFractionDigits : decimals !== undefined ? decimals : 2,
      maximumFractionDigits : decimals !== undefined ? decimals : 2,
    });
  }

  window.formatINR = formatINR;
  window.formatNum = formatNum;

  /* ═══════════════════════════════════════════════════
     13. AUTO-FORMAT AMOUNT INPUTS
     Add class="input-inr" to auto-format on blur.
  ═══════════════════════════════════════════════════ */

  document.querySelectorAll('input.input-inr').forEach(function (input) {
    input.addEventListener('focus', function () {
      // Show raw number on focus
      this.value = this.value.replace(/[^0-9.]/g, '');
    });
    input.addEventListener('blur', function () {
      const num = parseFloat(this.value);
      if (!isNaN(num)) {
        this.value = num.toFixed(2);
      }
    });
  });

  /* ═══════════════════════════════════════════════════
     14. TAB SWITCHING (no-backend)
     Add data-tab-group="groupName" to tab buttons,
     data-tab="id" to button, data-tab-panel="id" to panels.
  ═══════════════════════════════════════════════════ */

  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const group  = btn.getAttribute('data-tab-group');
      const target = btn.getAttribute('data-tab');

      // Deactivate all buttons in group
      document.querySelectorAll('[data-tab-group="' + group + '"]').forEach(function (b) {
        b.classList.remove('tab-active');
      });

      // Hide all panels in group
      document.querySelectorAll('[data-tab-panel][data-tab-group="' + group + '"]').forEach(function (p) {
        p.style.display = 'none';
      });

      btn.classList.add('tab-active');

      const panel = document.querySelector('[data-tab-panel="' + target + '"][data-tab-group="' + group + '"]');
      if (panel) panel.style.display = '';
    });
  });

  // Auto-activate first tab in each group
  (function () {
    const groups = {};
    document.querySelectorAll('[data-tab]').forEach(function (btn) {
      const g = btn.getAttribute('data-tab-group');
      if (!groups[g]) {
        groups[g] = btn;
        btn.click();
      }
    });
  })();

  /* ═══════════════════════════════════════════════════
     15. PRINT HELPER
  ═══════════════════════════════════════════════════ */

  window.printPage = function () {
    window.print();
  };

  /* ═══════════════════════════════════════════════════
     16. DROPDOWN MENUS (action menus in table rows)
     Add class="dropdown-toggle" + data-dropdown="menuId"
  ═══════════════════════════════════════════════════ */

  document.addEventListener('click', function (e) {
    const toggle = e.target.closest('.dropdown-toggle');

    // Close all open dropdowns first
    document.querySelectorAll('.dropdown-menu.dropdown--open').forEach(function (menu) {
      if (toggle && menu.id === toggle.getAttribute('data-dropdown')) return;
      menu.classList.remove('dropdown--open');
    });

    if (!toggle) return;

    const menuId = toggle.getAttribute('data-dropdown');
    const menu   = document.getElementById(menuId);
    if (!menu) return;

    e.stopPropagation();

    const open = menu.classList.contains('dropdown--open');
    menu.classList.toggle('dropdown--open', !open);

    // Position: check if it would overflow bottom
    if (!open) {
      const rect    = menu.getBoundingClientRect();
      const vpH     = window.innerHeight;
      if (rect.bottom > vpH) {
        menu.classList.add('dropdown--up');
      } else {
        menu.classList.remove('dropdown--up');
      }
    }
  });

  /* ═══════════════════════════════════════════════════
     17. MODAL SYSTEM
     showModal(id) / closeModal(id)
     Elements: .modal[id] > .modal-backdrop + .modal-box
  ═══════════════════════════════════════════════════ */

  function showModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('modal--open');
    document.body.classList.add('modal-open');
  }

  function closeModal(id) {
    const modal = id
      ? document.getElementById(id)
      : document.querySelector('.modal--open');
    if (!modal) return;
    modal.classList.remove('modal--open');
    document.body.classList.remove('modal-open');
  }

  window.showModal  = showModal;
  window.closeModal = closeModal;

  // Close modal on backdrop click
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('modal')) closeModal();
    if (e.target.closest('[data-modal-close]')) {
      const btn = e.target.closest('[data-modal-close]');
      closeModal(btn.getAttribute('data-modal-close') || undefined);
    }
    if (e.target.closest('[data-modal-open]')) {
      const btn = e.target.closest('[data-modal-open]');
      showModal(btn.getAttribute('data-modal-open'));
    }
  });

  /* ═══════════════════════════════════════════════════
     18. LOADING BUTTON STATE
     Call setLoading(btn, true/false) for async actions.
  ═══════════════════════════════════════════════════ */

  function setLoading(btnOrId, loading) {
    const btn = typeof btnOrId === 'string'
      ? document.getElementById(btnOrId)
      : btnOrId;
    if (!btn) return;

    if (loading) {
      btn._originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML =
        '<svg class="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
          '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>' +
        '</svg>' +
        '<span>Please wait…</span>';
    } else {
      btn.disabled = false;
      if (btn._originalHtml) {
        btn.innerHTML = btn._originalHtml;
        delete btn._originalHtml;
      }
    }
  }

  window.setLoading = setLoading;

  /* ═══════════════════════════════════════════════════
     19. INPUT CHARACTER COUNTER
     Add data-maxlength="N" + data-counter-target="spanId"
  ═══════════════════════════════════════════════════ */

  document.querySelectorAll('[data-maxlength]').forEach(function (input) {
    const max       = parseInt(input.getAttribute('data-maxlength'));
    const targetId  = input.getAttribute('data-counter-target');
    const target    = targetId ? document.getElementById(targetId) : null;
    if (!target) return;

    input.setAttribute('maxlength', max);

    function update() {
      const remaining = max - input.value.length;
      target.textContent = remaining + ' left';
      target.style.color = remaining < 10 ? 'var(--red)' : '';
    }

    input.addEventListener('input', update);
    update();
  });

  /* ═══════════════════════════════════════════════════
     20. PAGE LOAD PROGRESS BAR
  ═══════════════════════════════════════════════════ */

  (function initProgressBar() {
    const bar = document.createElement('div');
    bar.className = 'page-progress';
    document.body.appendChild(bar);

    let progress = 0;
    let interval = null;

    function start() {
      progress = 0;
      bar.style.width = '0%';
      bar.style.opacity = '1';
      interval = setInterval(function () {
        if (progress < 85) {
          progress += Math.random() * 8;
          bar.style.width = Math.min(progress, 85) + '%';
        }
      }, 120);
    }

    function finish() {
      clearInterval(interval);
      bar.style.width = '100%';
      setTimeout(function () {
        bar.style.opacity = '0';
        setTimeout(function () { bar.style.width = '0%'; }, 300);
      }, 300);
    }

    // Trigger on navigation link clicks
    document.addEventListener('click', function (e) {
      const link = e.target.closest('a[href]');
      if (!link) return;
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript') ||
          link.target === '_blank' || e.ctrlKey || e.metaKey) return;
      start();
    });

    // Finish on page load
    window.addEventListener('load', finish);

    window._progressStart  = start;
    window._progressFinish = finish;
  })();

  /* ═══════════════════════════════════════════════════
     21. RESPONSIVE TABLE SCROLL HINT
     On mobile, tables that overflow show a scroll hint.
  ═══════════════════════════════════════════════════ */

  (function initTableScrollHint() {
    document.querySelectorAll('.table-wrap').forEach(function (wrap) {
      function checkScroll() {
        const overflows = wrap.scrollWidth > wrap.clientWidth;
        wrap.classList.toggle('table-wrap--scrollable', overflows);
      }
      checkScroll();
      window.addEventListener('resize', checkScroll);
    });
  })();

  /* ═══════════════════════════════════════════════════
     22. AUTO-HIDE TOPBAR ON SCROLL (mobile)
  ═══════════════════════════════════════════════════ */

  (function initTopbarScroll() {
    const topbar = document.querySelector('.topbar');
    if (!topbar) return;

    let lastY   = 0;
    let ticking = false;

    window.addEventListener('scroll', function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          const y = window.scrollY;
          // Only on mobile
          if (window.innerWidth < 1024) {
            if (y > lastY && y > 60) {
              topbar.classList.add('topbar--hidden');
            } else {
              topbar.classList.remove('topbar--hidden');
            }
          }
          lastY   = y;
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  })();

  /* ═══════════════════════════════════════════════════
     INIT COMPLETE
  ═══════════════════════════════════════════════════ */

  console.log('[JewelBill UI] ui.js loaded ✓');

})();