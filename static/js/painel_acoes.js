// static/js/painel_acoes.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Painel de Ações carregado!');

    // Lógica para calcular as estatísticas dos cards
    const calcularStats = () => {
        const stats = { pendente: 0, 'em-andamento': 0, concluida: 0, atrasada: 0 };
        const badges = document.querySelectorAll('.modern-table .badge');
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);

        badges.forEach(badge => {
            const statusClass = Array.from(badge.classList).find(c => c.startsWith('bg-'));
            if (!statusClass) return;

            const status = statusClass.replace('bg-', '');
            const row = badge.closest('tr');
            const prazoIndicator = row?.querySelector('.prazo-indicator');

            if (status === 'warning') { // Pendente
                stats.pendente++;
                if (prazoIndicator && new Date(prazoIndicator.dataset.prazo) < hoje) {
                    stats.atrasada++;
                }
            } else if (status === 'info') { // Em andamento
                stats['em-andamento']++;
            } else if (status === 'success') { // Concluída
                stats.concluida++;
            } else if (status === 'danger') { // Atrasada (se houver um status específico)
                stats.atrasada++;
            }
        });

        document.getElementById('stat-pendente').textContent = stats.pendente;
        document.getElementById('stat-em-andamento').textContent = stats['em-andamento'];
        document.getElementById('stat-concluida').textContent = stats.concluida;
        document.getElementById('stat-atrasada').textContent = stats.atrasada;

        if (stats.atrasada > 0) {
            document.querySelector('.stat-card.atrasada')?.classList.add('pulse');
        }
    };

    // Lógica para colorir os indicadores de prazo
    const colorirPrazos = () => {
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        const prazos = document.querySelectorAll('.prazo-indicator');
        
        prazos.forEach(prazo => {
            if (!prazo.dataset.prazo) return;
            const prazoDate = new Date(prazo.dataset.prazo);
            const diffDays = Math.ceil((prazoDate - hoje) / (1000 * 60 * 60 * 24));

            prazo.classList.remove('urgente', 'proximo', 'normal');
            prazo.innerHTML = `<i class="fa-solid fa-calendar-alt"></i> ${prazo.textContent.trim()}`; // Reset icon

            if (diffDays < 0) {
                prazo.classList.add('urgente');
                prazo.querySelector('i').className = 'fa-solid fa-exclamation-circle';
            } else if (diffDays <= 3) {
                prazo.classList.add('proximo');
                prazo.querySelector('i').className = 'fa-solid fa-clock';
            } else {
                prazo.classList.add('normal');
            }
        });
    };

    // Lógica para destacar filtros ativos
    const destacarFiltrosAtivos = (limparUrl) => {
        const urlParams = new URLSearchParams(window.location.search);
        const hasFiltros = Array.from(urlParams.keys()).some(key => key.startsWith('filtro_'));
        
        if (hasFiltros) {
            const filtrosCard = document.querySelector('.filtros-card');
            if (filtrosCard) {
                filtrosCard.style.borderLeft = '5px solid var(--success-solid)';
                const header = filtrosCard.querySelector('.filtros-header');
                if (header && !header.querySelector('.filtro-ativo-badge')) {
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-success filtro-ativo-badge';
                    badge.innerHTML = '<i class="fa-solid fa-circle-check"></i> Filtros Ativos';
                    badge.style.marginLeft = 'auto';
                    header.appendChild(badge);
                }
            }
        }
        return hasFiltros;
    };

    // Lógica para feedback visual no botão de filtro
    const feedbackBotaoFiltro = () => {
        const filterForm = document.querySelector('.filtros-card form');
        if (filterForm) {
            filterForm.addEventListener('submit', function() {
                const filterBtn = this.querySelector('button[type="submit"]');
                if (filterBtn) {
                    filterBtn.disabled = true;
                    filterBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Filtrando...';
                }
            });
        }
    };
    
    // ATALHOS DE TECLADO E NAVEGAÇÃO
    function configurarAtalhos(limparUrl, hasFiltros) {
        const rows = document.querySelectorAll('.modern-table tbody tr:not(:has(.empty-state))');
        let selectedRow = -1;

        document.addEventListener('keydown', function(e) {
            if (e.target.matches('input, textarea, select')) return;

            switch (e.key) {
                case 'f':
                case 'F':
                    e.preventDefault();
                    document.getElementById('id_filtro_responsavel')?.focus();
                    break;
                case 'Escape':
                    if (hasFiltros) window.location.href = limparUrl;
                    break;
                case 'ArrowDown':
                    if (rows.length === 0) return;
                    e.preventDefault();
                    selectedRow = Math.min(selectedRow + 1, rows.length - 1);
                    highlightRow(rows, selectedRow);
                    break;
                case 'ArrowUp':
                    if (rows.length === 0) return;
                    e.preventDefault();
                    selectedRow = Math.max(selectedRow - 1, 0);
                    highlightRow(rows, selectedRow);
                    break;
                case 'Enter':
                    if (selectedRow >= 0 && rows[selectedRow]) {
                        e.preventDefault();
                        rows[selectedRow].click();
                    }
                    break;
            }
        });

        function highlightRow(rows, selectedIdx) {
            rows.forEach((row, index) => {
                row.style.outline = (index === selectedIdx) ? '3px solid var(--primary-solid)' : 'none';
                if (index === selectedIdx) {
                    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        }
    }

    // --- EXECUÇÃO ---
    const limparFiltrosUrl = document.querySelector('.btn-clear')?.href;
    if (limparFiltrosUrl) {
        calcularStats();
        colorirPrazos();
        const filtrosAtivos = destacarFiltrosAtivos(limparFiltrosUrl);
        feedbackBotaoFiltro();
        configurarAtalhos(limparFiltrosUrl, filtrosAtivos);
    }
});