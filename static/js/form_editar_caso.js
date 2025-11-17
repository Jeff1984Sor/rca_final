// static/js/form_editar_caso.js
function initEditarCasoForm(urls) {
    console.log('✅ Form de Editar Caso carregado!');

    const mainForm = document.querySelector('form.needs-validation');
    if (!mainForm) return;

    // --- LÓGICA DOS GRUPOS REPETÍVEIS (FORMSETS) ---
    const initFormsets = () => {
        // Adicionar novo form
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

        // Remover form
        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.delete-grupo-btn');
            if (!btn) return;
            e.preventDefault();

            if (!confirm('⚠️ Tem certeza que deseja remover este item?')) return;
            
            const formWrapper = btn.closest('.grupo-form');
            const deleteInput = formWrapper.querySelector('input[name$="-DELETE"]');

            if (deleteInput) { // Marcar para deleção no backend
                deleteInput.checked = true;
                formWrapper.style.display = 'none';
            } else { // Apenas remover do DOM (era um form novo)
                formWrapper.remove();
            }
        });
    };

    // --- AVISO DE ALTERAÇÕES NÃO SALVAS ---
    const setupUnsavedChangesWarning = () => {
        let formChanged = false;
        mainForm.addEventListener('change', () => { formChanged = true; });
        mainForm.addEventListener('submit', () => { formChanged = false; });
        
        const cancelBtn = document.querySelector('.btn-secondary');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', (e) => {
                if (formChanged && !confirm('⚠️ Deseja realmente cancelar? As alterações serão perdidas.')) {
                    e.preventDefault();
                } else {
                    formChanged = false; // Permite a navegação
                }
            });
        }
        
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
            if (e.key === 'Escape') {
                document.querySelector('.btn-secondary')?.click();
            }
        });
    };

    // --- EXECUÇÃO ---
    initFormsets();
    setupUnsavedChangesWarning();
    setupShortcuts();

    console.log('💡 Atalhos: Ctrl+S (Salvar), ESC (Cancelar)');
}