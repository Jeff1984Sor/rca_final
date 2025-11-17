// static/js/dashboard.js
function initDashboard(config) {
    console.log('✅ Dashboard carregado com sucesso!');

    // --- GRÁFICO DE PIZZA (CHART.JS) ---
    const initPizzaChart = () => {
        const pizzaCtx = document.getElementById('pizzaStatusChart');
        if (!pizzaCtx || !config.chartData) return;

        new Chart(pizzaCtx, {
            type: 'doughnut',
            data: {
                labels: config.chartData.labels, 
                datasets: [{
                    label: 'Quantidade de Casos', 
                    data: config.chartData.data,
                    backgroundColor: ['#CC5500', '#10b981', '#f59e0b', '#ef4444', '#0ea5e9', '#8b5cf6'],
                    borderColor: '#ffffff', 
                    borderWidth: 3, 
                    hoverOffset: 10
                }]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: true,
                plugins: { 
                    legend: { position: 'right', labels: { padding: 15, font: { size: 13, weight: '600' }}},
                    tooltip: { backgroundColor: 'rgba(0, 0, 0, 0.8)', padding: 12, titleFont: { size: 14, weight: 'bold' }, bodyFont: { size: 13 }, borderColor: '#CC5500', borderWidth: 2 }
                },
                animation: { animateScale: true, animateRotate: true }
            }
        });
    };

    // --- ANIMAÇÕES E EFEITOS VISUAIS ---
    const animateTableRows = () => {
        const rows = document.querySelectorAll('.data-table tbody tr');
        rows.forEach((row, index) => {
            row.style.opacity = '0';
            row.style.transform = 'translateY(10px)';
            setTimeout(() => {
                row.style.transition = 'all 0.3s ease-out';
                row.style.opacity = '1';
                row.style.transform = 'translateY(0)';
            }, index * 40);
        });
    };

    const highlightActiveFilters = () => {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('data_inicio') || urlParams.has('data_fim')) {
            const cardHeader = document.querySelector('.filtros-header');
            if (cardHeader && !cardHeader.querySelector('.filter-active-badge')) {
                const badge = document.createElement('span');
                badge.className = 'badge bg-success filter-active-badge';
                badge.innerHTML = '<i class="fa-solid fa-filter"></i> Período Ativo';
                badge.style.marginLeft = 'auto';
                cardHeader.appendChild(badge);
            }
        }
    };
    
    // --- ATALHOS DE TECLADO ---
    const setupShortcuts = () => {
        document.addEventListener('keydown', (e) => {
            if (e.target.matches('input, textarea, select')) return;
            
            const periodUrls = config.urls.periods || {};
            const keyMap = { 'h': periodUrls.hoje, 's': periodUrls.semana, 'm': periodUrls.mes };
            
            if (keyMap[e.key.toLowerCase()]) {
                e.preventDefault();
                window.location.href = keyMap[e.key.toLowerCase()];
            }
        });
    };

    // --- EXECUÇÃO ---
    initPizzaChart();
    animateTableRows();
    highlightActiveFilters();
    setupShortcuts();
    
    console.log('💡 Atalhos disponíveis: H (Hoje), S (Semana), M (Mês)');
}