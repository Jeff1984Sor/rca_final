// static/js/detalhes_equipamento.js
function initDetalhesEquipamento(urls) {
    console.log('✅ Detalhes do equipamento carregados!');

    // Animação dos cards ao carregar
    const cards = document.querySelectorAll('.info-card, .observacoes-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'all 0.4s ease-out';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });

    // Funcionalidade de copiar valores ao clicar
    const infoValues = document.querySelectorAll('.info-value.copyable:not(.empty)');
    infoValues.forEach(value => {
        value.title = 'Clique para copiar';
        value.addEventListener('click', function() {
            const text = this.textContent.trim();
            navigator.clipboard.writeText(text).then(() => {
                const originalText = this.innerHTML;
                this.style.color = 'var(--success-solid)';
                this.innerHTML = '<i class="fa-solid fa-check"></i> Copiado!';
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.style.color = '';
                }, 1500);
            }).catch(err => {
                console.error('Erro ao copiar:', err);
            });
        });
    });

    // Atalhos de teclado
    document.addEventListener('keydown', function(e) {
        if (e.target.matches('input, textarea, select')) return;

        if ((e.key === 'e' || e.key === 'E') && urls.editUrl) {
            window.location.href = urls.editUrl;
        }
        if (e.key === 'Escape' && urls.listUrl) {
            window.location.href = urls.listUrl;
        }
    });

    console.log('💡 Dicas:');
    console.log('   - Clique em qualquer valor para copiar');
    console.log('   - Pressione "E" para editar');
    console.log('   - Pressione ESC para voltar');
}