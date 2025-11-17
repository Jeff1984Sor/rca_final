// static/js/form_export_selecao.js
function initFormExportSelecao(urls) {
    console.log('✅ Exportação Dinâmica carregada!');

    const form = document.querySelector('form');
    const clienteSelect = document.getElementById('cliente-select');
    const produtoSelect = document.getElementById('produto-select');
    const submitBtn = document.getElementById('submitBtn');
    const previewBox = document.getElementById('preview');

    if (!form || !clienteSelect || !produtoSelect || !submitBtn || !previewBox) return;

    const previewClienteEl = document.getElementById('previewCliente');
    const previewProdutoEl = document.getElementById('previewProduto');

    const updateUI = () => {
        const clienteValido = clienteSelect.value !== '';
        const produtoValido = produtoSelect.value !== '';
        const formValido = clienteValido && produtoValido;

        // Habilita/desabilita o botão
        submitBtn.disabled = !formValido;
        submitBtn.style.opacity = formValido ? '1' : '0.5';
        submitBtn.style.cursor = formValido ? 'pointer' : 'not-allowed';

        // Mostra/esconde o preview
        if (formValido) {
            previewClienteEl.textContent = clienteSelect.options[clienteSelect.selectedIndex].text;
            previewProdutoEl.textContent = produtoSelect.options[produtoSelect.selectedIndex].text;
            previewBox.classList.add('visible');
        } else {
            previewBox.classList.remove('visible');
        }

        // Feedback visual nos selects
        clienteSelect.classList.toggle('is-valid', clienteValido);
        produtoSelect.classList.toggle('is-valid', produtoValido);
    };

    clienteSelect.addEventListener('change', updateUI);
    produtoSelect.addEventListener('change', updateUI);

    form.addEventListener('submit', (e) => {
        if (!form.checkValidity()) {
            e.preventDefault();
            alert('⚠️ Por favor, selecione cliente e produto!');
        } else {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Gerando...';
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && urls.cancelUrl) {
            if (confirm('⚠️ Deseja cancelar a exportação?')) {
                window.location.href = urls.cancelUrl;
            }
        }
        if (e.key === 'Enter' && !submitBtn.disabled) {
            e.preventDefault();
            form.submit();
        }
    });

    console.log('💡 Atalhos disponíveis: ESC (Cancelar), Enter (Gerar Exportação)');
}