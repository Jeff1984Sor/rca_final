// static/js/form_equipamento.js
function initEquipamentoForm(cancelUrl) {
    console.log('✅ Formulário de equipamento carregado!');

    const form = document.getElementById('equipamentoForm');
    const submitBtn = document.getElementById('submitBtn');
    const allInputs = form.querySelectorAll('input, select, textarea');

    if (!form || !submitBtn) return;

    // --- LÓGICA DE INTERATIVIDADE ---

    // Contador de caracteres para o campo de observações
    const observacoesField = form.querySelector('textarea[name="observacoes"]');
    if (observacoesField) {
        const charCounter = document.getElementById('char-counter');
        const charCount = document.getElementById('char-count');

        const updateCounter = () => {
            const length = observacoesField.value.length;
            charCount.textContent = length;
            charCounter.classList.toggle('warning', length > 500 && length <= 800);
            charCounter.classList.toggle('danger', length > 800);
        };
        observacoesField.addEventListener('input', updateCounter);
        updateCounter();
    }

    // Validação em tempo real (on blur e on input)
    const requiredInputs = form.querySelectorAll('[required]');
    requiredInputs.forEach(input => {
        const validate = () => {
            const isValid = input.value.trim() !== '';
            input.classList.toggle('is-invalid', !isValid);
            input.classList.toggle('is-valid', isValid);
        };
        input.addEventListener('blur', validate);
        input.addEventListener('input', () => {
            if (input.classList.contains('is-invalid')) validate();
        });
    });

    // Feedback visual no envio
    let isSubmitting = false;
    form.addEventListener('submit', function() {
        isSubmitting = true;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    });

    // Aviso de alterações não salvas
    let formChanged = false;
    allInputs.forEach(input => {
        input.addEventListener('change', () => { formChanged = true; });
    });
    window.addEventListener('beforeunload', (e) => {
        if (formChanged && !isSubmitting) {
            e.preventDefault();
            e.returnValue = '';
            return '';
        }
    });

    // --- ATALHOS DE TECLADO ---
    document.addEventListener('keydown', function(e) {
        if (e.target.matches('input, textarea, select')) return;

        // Ctrl+S para salvar
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            form.submit();
        }
        // ESC para cancelar
        if (e.key === 'Escape') {
            e.preventDefault();
            if (formChanged) {
                if (confirm('Deseja realmente cancelar? As alterações não salvas serão perdidas.')) {
                    window.location.href = cancelUrl;
                }
            } else {
                window.location.href = cancelUrl;
            }
        }
    });

    console.log('💡 Dicas:');
    console.log('   - Pressione Ctrl+S para salvar');
    console.log('   - Pressione ESC para cancelar');
}