/**
 * JewelBill — ui.js
 *
 * Handles: sidebar, toasts, flash messages, ripple,
 *          active nav detection, page-load progress bar,
 *          responsive table scroll hint, topbar auto-hide,
 *          tab switching (data-tab / data-tab-group).
 *
 * Removed (unused): showConfirm, live table search (data-search-target),
 *   sortable headers (data-sort), tooltips (data-tip), clipboard (data-copy),
 *   dirty-form guard, skeleton loaders, formatINR/formatNum/input-inr,
 *   printPage, dropdown-toggle, setLoading, modal system (showModal/closeModal),
 *   data-maxlength counter, flashMessages renderer.
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

  window.openSidebar  = openSidebar;
  window.closeSidebar = closeSidebar;

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });

  const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener('click', function () {
      document.body.classList.toggle('sidebar-collapsed');
      const collapsed = document.body.classList.contains('sidebar-collapsed');
      localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
    });
  }

  if (window.innerWidth >= 1024) {
    if (localStorage.getItem('sidebarCollapsed') === '1') {
      document.body.classList.add('no-transition');
      document.body.classList.add('sidebar-collapsed');
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          document.body.classList.remove('no-transition');
        });
      });
    }
  }

  /* ═══════════════════════════════════════════════════
     2. ACTIVE NAV AUTO-DETECTION
  ═══════════════════════════════════════════════════ */

  (function markActiveNav() {
    const path = window.location.pathname;

    function markBestMatch(selector) {
      const items = Array.from(document.querySelectorAll(selector));
      if (!items.length) return;
      if (items.some(function (item) { return item.classList.contains('active'); })) return;

      let bestItem = null;
      let bestLen  = -1;

      items.forEach(function (item) {
        const href = item.getAttribute('href');
        if (!href || href === '#') return;
        const exact  = href === path;
        const prefix = href !== '/' && (path === href || path.startsWith(href + '/'));
        if (!exact && !prefix) return;
        if (href.length > bestLen) { bestLen = href.length; bestItem = item; }
      });

      if (bestItem) bestItem.classList.add('active');
    }

    markBestMatch('.nav-item');
    markBestMatch('.bottom-nav-item');
  })();

  /* ═══════════════════════════════════════════════════
     3. TOAST NOTIFICATION SYSTEM
  ═══════════════════════════════════════════════════ */

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
    const msgEl  = toast.querySelector('.toast-msg');
    if (iconEl) iconEl.innerHTML  = (icons[type] || icons.info);
    if (msgEl)  msgEl.textContent = message == null ? '' : String(message);

    toast.querySelector('.toast-close').addEventListener('click', function () {
      dismissToast(toast);
    });

    container.appendChild(toast);

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

  window.showToast = showToast;

  /* ═══════════════════════════════════════════════════
     4. RIPPLE EFFECT on buttons
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
     5. PAGE LOAD PROGRESS BAR
  ═══════════════════════════════════════════════════ */

  (function initProgressBar() {
    const bar = document.createElement('div');
    bar.className = 'page-progress';
    document.body.appendChild(bar);

    let progress = 0;
    let interval = null;

    function start() {
      progress = 0;
      bar.style.width   = '0%';
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

    document.addEventListener('click', function (e) {
      const link = e.target.closest('a[href]');
      if (!link) return;
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript') ||
          link.target === '_blank' || e.ctrlKey || e.metaKey) return;
      start();
    });

    window.addEventListener('load', finish);

    window._progressStart  = start;
    window._progressFinish = finish;
  })();

  /* ═══════════════════════════════════════════════════
     6. RESPONSIVE TABLE SCROLL HINT
  ═══════════════════════════════════════════════════ */

  (function initTableScrollHint() {
    document.querySelectorAll('.table-wrap').forEach(function (wrap) {
      function checkScroll() {
        wrap.classList.toggle('table-wrap--scrollable', wrap.scrollWidth > wrap.clientWidth);
      }
      checkScroll();
      window.addEventListener('resize', checkScroll);
    });
  })();

  /* ═══════════════════════════════════════════════════
     7. AUTO-HIDE TOPBAR ON SCROLL (mobile)
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