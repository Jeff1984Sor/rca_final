// static/js/lista_equipamentos.js
function initListaEquipamentos(urls) {
    console.log('✅ Gestão de Equipamentos carregada!');

    const tableRows = document.querySelectorAll('.modern-table tbody tr:not(:has(.empty-state))');
    
    // Calcula as estatísticas dos cards
    const calcularStats = () => {
        let stats = { total: 0, ativos: 0, manutencao: 0, inativos: 0 };
        
        tableRows.forEach(row => {
            stats.total++;
            const badge = row.querySelector('.badge');
            if (badge) {
                const statusClass = Array.from(badge.classList).find(c => c.startsWith('badge-'));
                if (statusClass) {
                    const status = statusClass.replace('badge-', '');
                    if (status === 'ativo') stats.ativos++;
                    else if (status === 'manutencao') stats.manutencao++;
                    else if (status === 'inativo') stats.inativos++;
                }
            }
        });

        document.getElementById('total-equipamentos').textContent = stats.total;
        document.getElementById('total-ativos').textContent = stats.ativos;
        document.getElementById('total-manutencao').textContent = stats.manutencao;
        document.getElementById('total-inativos').textContent = stats.inativos;
    };

    // Animação de entrada das linhas da tabela
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

    // Adiciona um contador ao cabeçalho da tabela
    const addTableCounter = () => {
        const total = tableRows.length;
        if (total > 0) {
            const headerDiv = document.querySelector('.table-header');
            if (headerDiv && !headerDiv.querySelector('.table-counter')) {
                const counter = document.createElement('span');
                counter.className = 'table-counter';
                counter.style.cssText = 'margin-left: auto; font-size: 0.9rem; font-weight: 600; opacity: 0.7;';
                counter.innerHTML = `<i class="fa-solid fa-list-ol"></i> ${total} equipamento${total > 1 ? 's' : ''}`;
                headerDiv.appendChild(counter);
            }
        }
    };
    
    // Configura os atalhos de teclado
    const setupShortcuts = () => {
        document.addEventListener('keydown', (e) => {
            if (e.target.matches('input, textarea, select')) return;
            
            if ((e.key === 'n' || e.key === 'N') && urls.createUrl) {
                e.preventDefault();
                window.location.href = urls.createUrl;
            }
            if ((e.key === 'f' || e.key === 'F')) {
                e.preventDefault();
                document.getElementById('id_filtro_nome')?.focus();
            }
        });
    };

    // Execução
    calcularStats();
    animateRows();
    addTableCounter();
    setupShortcuts();

    console.log('💡 Dicas de uso:');
    console.log('   - Pressione "N" para adicionar novo equipamento');
    console.log('   - Pressione "F" para focar no filtro de nome');
}