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
