// static/js/visao_prazo.js
function initVisaoPrazo(urls) {
    console.log('✅ Visão por Prazo carregada!');

    const tableRows = document.querySelectorAll('.data-table tbody tr:not(:has(.empty-state))');
    
    // --- LÓGICA DE INTERATIVIDADE ---
    
    // Contagem automática dos stats cards
    const calcularStats = () => {
        let stats = { vencidos: 0, urgentes: 0, atencao: 0, normal: 0 };
        tableRows.forEach(row => {
            const badge = row.querySelector('.badge');
            if (!badge) return;
            
            if (badge.classList.contains('bg-dark')) stats.vencidos++;
            else if (badge.classList.contains('bg-danger')) stats.urgentes++;
            else if (badge.classList.contains('bg-warning')) stats.atencao++;
            else if (badge.classList.contains('bg-success')) stats.normal++;
        });

        animateCounter('countVencidos', stats.vencidos);
        animateCounter('countUrgentes', stats.urgentes);
        animateCounter('countAtencao', stats.atencao);
        animateCounter('countNormal', stats.normal);

        if (stats.vencidos > 0) console.warn(`⚠️ ATENÇÃO: ${stats.vencidos} caso(s) com prazo vencido!`);
        if (stats.urgentes > 0) console.warn(`🔥 ${stats.urgentes} caso(s) urgente(s)!`);
    };

    // Animação do contador
    const animateCounter = (id, finalValue) => {
        const el = document.getElementById(id);
        if (!el) return;
        let current = 0;
        const increment = Math.max(1, finalValue / 50); // Anima em ~50 frames
        const timer = setInterval(() => {
            current += increment;
            if (current >= finalValue) {
                el.textContent = finalValue;
                clearInterval(timer);
            } else {
                el.textContent = Math.floor(current);
            }
        }, 20);
    };

    // Animação de entrada das linhas
    const animateRows = () => {
        tableRows.forEach((row, index) => {
            row.style.opacity = '0';
            row.style.transform = 'translateY(10px)';
            setTimeout(() => {
                row.style.transition = 'all 0.3s ease-out';
                row.style.opacity = '1';
                row.style.transform = 'translateY(0)';
            }, index * 40);
        });
    };
    
    // Tornar linhas da tabela clicáveis
    const makeRowsClickable = () => {
        tableRows.forEach(row => {
            row.style.cursor = 'pointer';
            row.addEventListener('click', () => {
                const link = row.querySelector('a');
                if (link) window.location.href = link.href;
            });
        });
    };

    // --- ATALHOS DE TECLADO ---
    const setupShortcuts = () => {
        document.addEventListener('keydown', (e) => {
            if (e.target.matches('input, textarea, select')) return;

            if (e.key.toLowerCase() === 'f') {
                e.preventDefault();
                document.getElementById('prazo_inicio')?.focus();
            }
            if (e.key === 'Escape' && urls.listUrl) {
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.toString() !== '') {
                    window.location.href = urls.listUrl;
                }
            }
        });
    };
    
    // --- EXECUÇÃO ---
    calcularStats();
    animateRows();
    makeRowsClickable();
    setupShortcuts();
    
    console.log('💡 Atalhos: F (Focar filtro), ESC (Limpar filtros)');
}