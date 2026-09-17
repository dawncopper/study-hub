/* 学习小站 StudyHub - 前端交互脚本（iOS 风格） */
(function () {
  'use strict';

  /* ---------- 6.2 明暗双模式 ---------- */
  var STORAGE_KEY = 'studyhub_theme';
  var root = document.documentElement;
  var themeBtn = document.getElementById('themeToggle');

  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    if (themeBtn) {
      themeBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) { saved = null; }
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(saved || (prefersDark ? 'dark' : 'light'));
  }

  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem(STORAGE_KEY, next); } catch (e) { /* ignore */ }
    });
  }

  /* ---------- 日期标签 ---------- */
  var todayLabel = document.getElementById('todayLabel');
  if (todayLabel) {
    var WEEK = ['日', '一', '二', '三', '四', '五', '六'];
    var now = new Date();
    todayLabel.textContent = (now.getMonth() + 1) + '月' + now.getDate() + '日 星期' + WEEK[now.getDay()];
  }

  /* ---------- 横幅自动消失 ---------- */
  var banners = document.querySelectorAll('.banner');
  banners.forEach(function (b) {
    setTimeout(function () {
      b.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
      b.style.opacity = '0';
      b.style.transform = 'translateY(-8px)';
      setTimeout(function () { b.remove(); }, 600);
    }, 4200);
  });

  /* ---------- 危险操作确认（data-confirm） ---------- */
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-confirm]') : null;
    if (el && !window.confirm(el.getAttribute('data-confirm') || '确定执行该操作吗？')) {
      e.preventDefault();
      e.stopPropagation();
    }
  });

  /* ---------- 表单提交 Loading 覆盖层 ---------- */
  var overlay = document.createElement('div');
  overlay.className = 'loading-overlay';
  overlay.innerHTML = '<div class="spinner"></div><div class="loading-text">正在处理…</div>';
  document.body.appendChild(overlay);

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form && form.matches('form')) {
      var action = (form.getAttribute('action') || '');
      var method = (form.getAttribute('method') || 'get').toLowerCase();
      // 站内表单提交显示 loading；GET 筛选表单除外
      if (method === 'post' && action.indexOf('http') !== 0) {
        var confirmed = true;
        var confirmBtn = form.querySelector('[data-confirm]');
        if (confirmBtn && !window.confirm(confirmBtn.getAttribute('data-confirm'))) {
          confirmed = false;
        }
        if (confirmed) {
          overlay.classList.add('show');
        } else {
          e.preventDefault();
        }
      }
    }
  });

  /* ---------- 仪表盘打卡矩阵：选择即保存 ---------- */
  document.querySelectorAll('.status-select').forEach(function (select) {
    select.addEventListener('change', function () {
      var form = select.closest('form');
      if (form) {
        overlay.classList.add('show');
        form.submit();
      }
    });
  });

  document.querySelectorAll('.quality-select').forEach(function (select) {
    select.addEventListener('change', function () {
      var status = select.closest('.matrix-cell').querySelector('.status-select');
      if (status && status.value === 'undone') {
        status.value = 'done';
      }
      var form = select.closest('form');
      if (form) {
        overlay.classList.add('show');
        form.submit();
      }
    });
  });

  /* ---------- 加载态：页面就绪后移除骨架 ---------- */
  var skeletons = document.querySelectorAll('.skeleton');
  if (skeletons.length) {
    setTimeout(function () {
      skeletons.forEach(function (s) { s.remove(); });
    }, 400);
  }
})();
