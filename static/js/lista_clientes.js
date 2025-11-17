// static/js/lista_clientes.js
function initListaClientes(urls) {
    console.log('✅ Gestão de Clientes carregada!');

    const tableRows = document.querySelectorAll('.data-table tbody tr:not(:has(.empty-state))');
    
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

    // Configura os atalhos de teclado
    const setupShortcuts = () => {
        document.addEventListener('keydown', (e) => {
            if (e.target.matches('input, textarea, select')) return;
            
            // 'N' para Novo Cliente
            if ((e.key === 'n' || e.key === 'N') && urls.createUrl) {
                e.preventDefault();
                window.location.href = urls.createUrl;
            }
            // 'F' para focar no filtro de nome
            if ((e.key === 'f' || e.key === 'F')) {
                e.preventDefault();
                document.getElementById('id_filtro_nome')?.focus();
            }
            // 'ESC' para limpar filtros
            if (e.key === 'Escape' && urls.listUrl) {
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.has('filtro_nome') || urlParams.has('filtro_tipo')) {
                    window.location.href = urls.listUrl;
                }
            }
        });
    };

    // Execução
    animateRows();
    setupShortcuts();

    console.log('💡 Atalhos disponíveis: N (Novo Cliente), F (Focar filtro), ESC (Limpar filtros)');
}