// static/js/form_acordo.js
function initAcordoForm(urls) {
    console.log('✅ Formulário de Acordo carregado!');

    const form = document.getElementById('acordoForm');
    if (!form) return;

    // --- LÓGICA DE INTERATIVIDADE ---
    
    // Máscara de moeda no valor total
    const valorInput = form.querySelector('input[name="valor_total"]');
    if (valorInput) {
        const formatarValor = () => {
            let value = valorInput.value.replace(/\D/g, '');
            if (value) {
                const numberValue = parseInt(value, 10) / 100;
                const formatted = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(numberValue);
                valorInput.value = formatted;
            }
        };
        valorInput.addEventListener('input', formatarValor);
        if (valorInput.value) formatarValor(); // Formata valor inicial
    }

    // Validação de número de parcelas
    const parcelasInput = form.querySelector('input[name="numero_parcelas"]');
    if (parcelasInput) {
        parcelasInput.addEventListener('input', () => {
            parcelasInput.value = parcelasInput.value.replace(/\D/g, ''); // Apenas números
            if (parseInt(parcelasInput.value) > 999) parcelasInput.value = '999';
        });
    }

    // Feedback visual no submit
    const submitBtn = document.getElementById('submitBtn');
    form.addEventListener('submit', (e) => {
        if (!form.checkValidity()) {
            e.preventDefault();
            form.querySelector(':invalid')?.focus();
        } else {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
        }
    });

    // --- ATALHOS DE TECLADO ---
    document.addEventListener('keydown', (e) => {
        if (e.target.matches('input, textarea, select')) return;

        if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); form.submit(); }
        if (e.key === 'Escape' && urls.cancelUrl) {
            if (confirm('⚠️ Deseja realmente cancelar?')) { window.location.href = urls.cancelUrl; }
        }
    });

    console.log('💡 Atalhos: Ctrl+S (Salvar), ESC (Cancelar)');
}