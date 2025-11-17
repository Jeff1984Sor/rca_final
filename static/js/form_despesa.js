// static/js/form_despesa.js
function initDespesaForm(urls) {
    console.log('✅ Formulário de Despesa carregado!');

    const form = document.getElementById('despesaForm');
    if (!form) return;

    // --- LÓGICA DE INTERATIVIDADE ---
    
    // Máscara e preview do valor
    const valorInput = form.querySelector('input[name="valor"]');
    const valorPreview = document.getElementById('valorPreview');
    const valorPreviewValue = document.getElementById('valorPreviewValue');
    if (valorInput && valorPreview) {
        const formatarValor = () => {
            let value = valorInput.value.replace(/\D/g, '');
            if (value) {
                const numberValue = parseInt(value, 10) / 100;
                const formatted = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(numberValue);
                valorInput.value = formatted;

                valorPreview.classList.add('visible');
                valorPreviewValue.textContent = formatted;
            } else {
                valorPreview.classList.remove('visible');
            }
        };
        valorInput.addEventListener('input', formatarValor);
        if (valorInput.value) formatarValor(); // Formata valor inicial
    }

    // Validação de data (não pode ser futura)
    const dataInput = form.querySelector('input[name="data_despesa"]');
    if (dataInput) {
        dataInput.addEventListener('change', () => {
            const dataEscolhida = new Date(dataInput.value + "T00:00:00"); // Adiciona T00 para evitar problemas de timezone
            const hoje = new Date();
            hoje.setHours(0, 0, 0, 0);
            if (dataEscolhida > hoje) {
                alert('⚠️ A data da despesa não pode ser futura!');
                dataInput.value = '';
                dataInput.focus();
            }
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