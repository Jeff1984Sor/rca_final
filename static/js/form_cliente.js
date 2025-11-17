// static/js/form_cliente.js
function initClienteForm(urls) {
    console.log('✅ Formulário de Cliente carregado!');

    const form = document.getElementById('clienteForm');
    if (!form) return;

    // --- LÓGICA DE INTERATIVIDADE ---

    // Preview do tipo de pessoa (PF/PJ)
    const tipoSelect = form.querySelector('select[name="tipo"]');
    const tipoPreview = document.getElementById('tipoPreview');
    if (tipoSelect && tipoPreview) {
        const tipoIcon = document.getElementById('tipoIcon');
        const tipoValue = document.getElementById('tipoValue');

        const updateTipoPreview = () => {
            const tipo = tipoSelect.value;
            if (tipo) {
                tipoPreview.classList.add('visible');
                const isPF = tipo === 'PF';
                tipoIcon.className = `fa-solid tipo-preview-icon ${isPF ? 'fa-user pf' : 'fa-building pj'}`;
                tipoValue.className = `tipo-preview-value ${isPF ? 'pf' : 'pj'}`;
                tipoValue.textContent = isPF ? 'Pessoa Física' : 'Pessoa Jurídica';
                tipoPreview.style.borderLeftColor = isPF ? 'var(--info-solid)' : 'var(--warning-solid)';
            } else {
                tipoPreview.classList.remove('visible');
            }
        };
        tipoSelect.addEventListener('change', updateTipoPreview);
        updateTipoPreview(); // Executa na inicialização
    }
    
    // Normalização do campo UF para maiúsculas e 2 caracteres
    const ufInput = form.querySelector('input[name="uf"]');
    if (ufInput) {
        ufInput.addEventListener('input', () => {
            ufInput.value = ufInput.value.toUpperCase().substring(0, 2);
        });
    }

    // Feedback visual no envio do formulário
    const submitBtn = document.getElementById('submitBtn');
    form.addEventListener('submit', () => {
        if (form.checkValidity()) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
        }
    });

    // --- ATALHOS DE TECLADO ---
    document.addEventListener('keydown', (e) => {
        if (e.target.matches('input, textarea, select')) return;

        // Ctrl+S para salvar
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            form.submit();
        }
        // ESC para cancelar
        if (e.key === 'Escape' && urls.listUrl) {
            e.preventDefault();
            if (confirm('⚠️ Deseja realmente cancelar? As alterações serão perdidas.')) {
                window.location.href = urls.listUrl;
            }
        }
    });

    console.log('💡 Atalhos disponíveis: Ctrl+S (Salvar), ESC (Cancelar)');
}