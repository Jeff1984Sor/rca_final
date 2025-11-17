// static/js/form_timesheet.js
function initTimesheetForm(urls) {
    console.log('✅ Formulário de Timesheet carregado!');

    const form = document.querySelector('form');
    if (!form) return;

    // --- LÓGICA DE INTERATIVIDADE ---

    // Máscara de tempo (HH:MM) para o campo 'tempo'
    const tempoInput = form.querySelector('input[name="tempo"]');
    if (tempoInput) {
        const formatTime = (e) => {
            let value = e.target.value.replace(/\D/g, '').substring(0, 4);
            if (value.length > 2) {
                e.target.value = `${value.substring(0, 2)}:${value.substring(2)}`;
            } else {
                e.target.value = value;
            }
        };

        const validateAndPadTime = (e) => {
            let parts = e.target.value.split(':');
            if (parts.length === 2) {
                let [hour, minute] = parts;
                hour = hour.padStart(2, '0');
                minute = minute.padStart(2, '0');
                if (parseInt(hour) > 23) hour = '23';
                if (parseInt(minute) > 59) minute = '59';
                e.target.value = `${hour}:${minute}`;
            }
        };

        tempoInput.addEventListener('input', formatTime);
        tempoInput.addEventListener('blur', validateAndPadTime);
    }

    // Feedback visual no envio do formulário
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

        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            form.submit();
        }
        if (e.key === 'Escape' && urls.cancelUrl) {
            e.preventDefault();
            if (confirm('⚠️ Deseja realmente cancelar?')) {
                window.location.href = urls.cancelUrl;
            }
        }
    });

    console.log('💡 Atalhos: Ctrl+S (Salvar), ESC (Cancelar)');
}