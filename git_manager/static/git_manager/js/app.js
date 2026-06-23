function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next === 'dark' ? '' : 'light');
    localStorage.setItem('theme', next);
}

function toggleAllPushLogDetails(open) {
    document.querySelectorAll('details.log-output').forEach(el => el.open = open);
}

(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') document.documentElement.setAttribute('data-theme', 'light');
})();

(function() {
    const currentPath = window.location.pathname;
    fetch('/api/repos/ids/')
        .then(r => r.json())
        .then(data => {
            if (!data.repos || data.repos.length === 0) return;
            const container = document.getElementById('nav-repos-sub');
            container.innerHTML = data.repos.map(repo => {
                const url = `/repos/${repo.id}/`;
                const isActive = currentPath === url || currentPath.startsWith(url);
                return `<a href="${url}" class="${isActive ? 'active-sub' : ''}">· ${repo.name}</a>`;
            }).join('');
        })
        .catch(() => {});
})();

// ── Tree view ─────────────────────────────────────────────────────

function loadTree(pk, path, container) {
    container = container || document.getElementById('git-tree');
    if (!container) return;
    container.innerHTML = '<div class="tree-loader">Chargement…</div>';
    fetch(`/repos/${pk}/tree/?path=${encodeURIComponent(path)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                container.innerHTML = `<div class="tree-loader" style="color:var(--danger)">${data.error}</div>`;
                return;
            }
            renderTree(data.entries, path, container, pk);
        })
        .catch(() => {
            container.innerHTML = '<div class="tree-loader" style="color:var(--danger)">Erreur de chargement</div>';
        });
}

function renderTree(entries, currentPath, container, pk) {
    if (!entries || entries.length === 0) {
        container.innerHTML = '<div class="tree-empty">Dossier vide</div>';
        return;
    }
    var html = '<div class="tree-list">';
    for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        var isDir = e.type === 'tree';
        var icon = isDir ? '📁' : '📄';
        var cls = isDir ? 'tree-dir' : 'tree-file';
        var sizeStr = '';
        if (e.size && e.size !== '-' && !isDir) {
            sizeStr = ' <span class="tree-size">' + formatSize(parseInt(e.size, 10)) + '</span>';
        }
        if (isDir) {
            html += '<div class="tree-item ' + cls + '" data-path="' + escapeHtml(e.path) + '">'
                + '<span class="tree-toggle" onclick="toggleTreeDir(' + pk + ',\'' + escapeJs(e.path) + '\', this)">▶</span> '
                + icon + ' ' + escapeHtml(e.name) + '</div>';
        } else {
            html += '<div class="tree-item ' + cls + '">'
                + '<span class="tree-toggle tree-toggle-spacer"></span> '
                + icon + ' ' + escapeHtml(e.name) + sizeStr + '</div>';
        }
    }
    html += '</div>';
    container.innerHTML = html;
}

function toggleTreeDir(pk, path, toggleEl) {
    var parent = toggleEl.parentElement;
    if (parent.classList.contains('tree-open')) {
        parent.classList.remove('tree-open');
        var sub = parent.querySelector('.tree-sub');
        if (sub) sub.remove();
        toggleEl.textContent = '▶';
        return;
    }
    toggleEl.textContent = '▼';
    parent.classList.add('tree-open');
    var sub = document.createElement('div');
    sub.className = 'tree-sub';
    sub.innerHTML = '<div class="tree-loader">Chargement…</div>';
    parent.appendChild(sub);
    fetch(`/repos/${pk}/tree/?path=${encodeURIComponent(path)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                sub.innerHTML = '<div class="tree-loader" style="color:var(--danger)">' + data.error + '</div>';
                return;
            }
            renderTree(data.entries, path, sub, pk);
        })
        .catch(() => {
            sub.innerHTML = '<div class="tree-loader" style="color:var(--danger)">Erreur</div>';
        });
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escapeJs(s) {
    return String(s).replace(/'/g,"\\'").replace(/"/g,'\\"');
}

(function() {
    var treeEl = document.getElementById('git-tree');
    if (treeEl) {
        var pk = treeEl.getAttribute('data-pk');
        if (pk) loadTree(pk, '.');
    }
})();
