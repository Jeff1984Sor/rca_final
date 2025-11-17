// static/js/kanban_board.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Kanban Board carregado!');

    // --- FUNÇÕES DE INICIALIZAÇÃO ---
    const calcularTotal = () => {
        const cards = document.querySelectorAll('.kanban-card');
        const totalCasosEl = document.getElementById('total-casos');
        if (totalCasosEl) {
            totalCasosEl.textContent = cards.length;
        }
    };

    const animateCards = () => {
        const cards = document.querySelectorAll('.kanban-card');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            setTimeout(() => {
                card.style.transition = 'all 0.4s ease-out';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 50);
        });
    };
    
    // --- MANIPULADORES DE EVENTOS ---
    const kanbanBoard = document.getElementById('kanban-board');
    if (kanbanBoard) {
        // Scroll horizontal suave com o scroll do mouse
        kanbanBoard.addEventListener('wheel', (e) => {
            if (e.deltaY !== 0) {
                e.preventDefault();
                kanbanBoard.scrollLeft += e.deltaY;
            }
        }, { passive: false });

        // Swipe horizontal para mobile
        if ('ontouchstart' in window) {
            let touchStartX = 0;
            kanbanBoard.addEventListener('touchstart', e => {
                touchStartX = e.changedTouches[0].screenX;
            }, { passive: true });
            kanbanBoard.addEventListener('touchend', e => {
                const touchEndX = e.changedTouches[0].screenX;
                const swipeThreshold = 50; // pixels
                if (touchEndX < touchStartX - swipeThreshold) {
                    kanbanBoard.scrollBy({ left: 300, behavior: 'smooth' });
                } else if (touchEndX > touchStartX + swipeThreshold) {
                    kanbanBoard.scrollBy({ left: -300, behavior: 'smooth' });
                }
            }, { passive: true });
        }
    }

    // Navegação por teclado
    let selectedColumn = 0;
    let selectedCard = -1;
    const columns = Array.from(document.querySelectorAll('.kanban-column'));
    
    document.addEventListener('keydown', (e) => {
        if (e.target.matches('input, textarea, select')) return;

        const handleNavigation = (key) => {
            if (columns.length === 0) return;
            e.preventDefault();

            switch (key) {
                case 'ArrowLeft':
                    selectedColumn = Math.max(0, selectedColumn - 1);
                    selectedCard = 0;
                    highlightColumn(selectedColumn);
                    break;
                case 'ArrowRight':
                    selectedColumn = Math.min(columns.length - 1, selectedColumn + 1);
                    selectedCard = 0;
                    highlightColumn(selectedColumn);
                    break;
                case 'ArrowDown':
                case 'ArrowUp':
                    const currentColumn = columns[selectedColumn];
                    const cards = currentColumn ? Array.from(currentColumn.querySelectorAll('.kanban-card')) : [];
                    if (cards.length > 0) {
                        const direction = (key === 'ArrowDown') ? 1 : -1;
                        selectedCard = (selectedCard + direction + cards.length) % cards.length;
                        highlightCard(cards, selectedCard);
                    }
                    break;
                case 'Enter':
                    const activeCard = columns[selectedColumn]?.querySelectorAll('.kanban-card')[selectedCard];
                    if (activeCard) activeCard.click();
                    break;
            }
        };

        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Enter'].includes(e.key)) {
            handleNavigation(e.key);
        }
    });

    const highlightColumn = (index) => {
        columns.forEach((col, i) => {
            col.style.outline = (i === index) ? '3px solid var(--primary-solid)' : 'none';
            if (i === index) col.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        });
        highlightCard(columns[index]?.querySelectorAll('.kanban-card'), 0);
    };

    const highlightCard = (cards, index) => {
        if (!cards) return;
        cards.forEach((card, i) => {
            card.style.outline = (i === index) ? '3px solid var(--info-solid)' : 'none';
            if (i === index) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    };

    // --- EXECUÇÃO ---
    calcularTotal();
    animateCards();

    // Log de estatísticas no console
    console.log('📊 Estatísticas do Kanban:');
    columns.forEach(column => {
        const title = column.querySelector('.column-title')?.textContent.trim();
        const count = column.querySelectorAll('.kanban-card').length;
        console.log(`   - ${title}: ${count} casos`);
    });
});