// static/js/form_criar_caso.js
function initCriarCasoForm(urls) {
    console.log('✅ Form de Criar Caso carregado!');

    const mainForm = document.querySelector('form.needs-validation');
    if (!mainForm) return;

    // --- LÓGICA DOS GRUPOS REPETÍVEIS (FORMSETS) ---
    const initFormsets = () => {
        document.querySelectorAll('.add-grupo-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const prefix = btn.dataset.formsetPrefix;
                const grupoId = btn.dataset.grupoId;
                const container = document.getElementById(`formset-container-${grupoId}`);
                const totalFormsInput = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
                const emptyFormHtml = document.getElementById(`empty-form-${grupoId}`)?.innerHTML;

                if (!emptyFormHtml) return;
                
                const newIndex = parseInt(totalFormsInput.value, 10);
                const newFormHtml = emptyFormHtml.replace(/__prefix__/g, newIndex);
                
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = newFormHtml;
                const newFormElement = tempDiv.firstElementChild;
                
                container.appendChild(newFormElement);
                totalFormsInput.value = newIndex + 1;

                newFormElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
        });

        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.delete-grupo-btn');
            if (!btn) return;
            e.preventDefault();

            if (!confirm('⚠️ Tem certeza que deseja remover este item?')) return;
            
            const formWrapper = btn.closest('.grupo-form');
            const deleteInput = formWrapper.querySelector('input[name$="-DELETE"]');

            if (deleteInput && deleteInput.value !== undefined) {
                deleteInput.checked = true;
                formWrapper.style.display = 'none';
            } else {
                formWrapper.remove();
            }
        });
    };

    // --- AVISO DE ALTERAÇÕES NÃO SALVAS ---
    const setupUnsavedChangesWarning = () => {
        let formChanged = false;
        mainForm.addEventListener('change', () => { formChanged = true; });
        mainForm.addEventListener('submit', () => { formChanged = false; });
        
        window.addEventListener('beforeunload', (e) => {
            if (formChanged) {
                e.preventDefault();
                e.returnValue = '';
                return '';
            }
        });
    };
    
    // --- ATALHOS DE TECLADO ---
    const setupShortcuts = () => {
        document.addEventListener('keydown', (e) => {
            if (e.target.matches('input, textarea, select')) return;

            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                mainForm.querySelector('button[type="submit"]')?.click();
            }
            if (e.key === 'Escape' && urls.cancelUrl) {
                if (confirm('⚠️ Deseja realmente cancelar?')) {
                    window.location.href = urls.cancelUrl;
                }
            }
        });
    };

    // --- FEEDBACK NO SUBMIT ---
    const setupSubmitFeedback = () => {
        const submitBtn = mainForm.querySelector('button[type="submit"]');
        if(submitBtn) {
            mainForm.addEventListener('submit', (e) => {
                if (mainForm.checkValidity()) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Criando...';
                }
            });
        }
    };

    // --- EXECUÇÃO ---
    initFormsets();
    setupUnsavedChangesWarning();
    setupShortcuts();
    setupSubmitFeedback();

    console.log('💡 Atalhos: Ctrl+S (Salvar), ESC (Cancelar)');
}