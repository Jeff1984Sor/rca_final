// static/js/detalhe_caso.js

/**
 * Inicializa todas as funcionalidades da página de detalhes do caso.
 * @param {object} config - Objeto de configuração passado pelo template.
 * @param {object} config.modelosAndamento - Dicionário com modelos de andamento.
 */
function initDetalheCaso(config) {
    
    // --- LÓGICA DAS ABAS (TABS) ---
    const setupTabs = () => {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');
        
        const activateTab = (tabId) => {
            if (!tabId) return;
            tabButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tabId));
            tabContents.forEach(content => content.classList.toggle('active', content.id === tabId));
        };
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.dataset.tab;
                activateTab(tabId);
                const url = new URL(window.location);
                url.searchParams.set('aba', tabId);
                window.history.pushState({}, '', url);
            });
        });

        const urlParams = new URLSearchParams(window.location.search);
        const initialTab = urlParams.get('aba') || 'detalhes';
        activateTab(initialTab);
    };

    // --- LÓGICA DOS MODAIS ---
    const setupModals = () => {
        window.openEditModal = (modalId) => {
            document.getElementById(`modal-${modalId}`)?.classList.add('active');
            document.body.style.overflow = 'hidden';
        };
        window.closeEditModal = (modalId) => {
            document.getElementById(`modal-${modalId}`)?.classList.remove('active');
            document.body.style.overflow = '';
        };
        window.closeModalOnOverlay = (event, modalId) => {
            if (event.target.classList.contains('edit-modal-overlay')) {
                closeEditModal(modalId);
            }
        };
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const activeModal = document.querySelector('.edit-modal-overlay.active');
                if (activeModal) {
                    const modalId = activeModal.id.replace('modal-', '');
                    closeEditModal(modalId);
                }
            }
        });
    };
    
    // --- LÓGICA DOS FORMULÁRIOS DAS ABAS ---
    const setupTabForms = () => {
        // Preenchimento automático do modelo de Andamento
        const selectModelo = document.querySelector('#andamentos select[name=modelo_andamento]');
        const textareaDescricao = document.querySelector('#andamentos textarea[name=descricao]');
        if (selectModelo && textareaDescricao && config.modelosAndamento) {
            selectModelo.addEventListener('change', () => {
                textareaDescricao.value = config.modelosAndamento[selectModelo.value] || '';
            });
        }
        
        // Máscara de tempo (HH:MM) para o formulário de Timesheet
        const tempoInput = document.querySelector('#timesheet input[name="tempo"]');
        if (tempoInput) {
            tempoInput.addEventListener('input', (e) => {
                let value = e.target.value.replace(/\D/g, '').substring(0, 4);
                if (value.length > 2) value = `${value.substring(0, 2)}:${value.substring(2)}`;
                e.target.value = value;
            });
        }
    };

    // --- EXECUÇÃO DAS FUNÇÕES DE SETUP ---
    setupTabs();
    setupModals();
    setupTabForms();

    console.log('✅ Página de Detalhes do Caso carregada!');
}


// ========================================
// 📁 FUNÇÃO GLOBAL PARA ATUALIZAR LISTA DE ARQUIVOS
// ========================================
window.updateFileList = function(input) {
    const parentForm = input.closest('form');
    if (!parentForm) return;
    
    const fileListPreview = parentForm.querySelector('.file-list-preview');
    if (fileListPreview && input.files.length > 0) {
        let fileNames = Array.from(input.files).map(file => file.name).join(', ');
        fileListPreview.textContent = fileNames.length > 100 
            ? `${input.files.length} arquivos selecionados.` 
            : `Selecionado(s): ${fileNames}`;
    } else if (fileListPreview) {
        fileListPreview.textContent = '';
    }
}

// ========================================
// 🎉 FUNÇÃO GLOBAL PARA NOTIFICAÇÕES (TOAST)
// ========================================
window.showToast = function(message, type = 'success') {
    // Injeta as animações do toast no <head> se ainda não existirem
    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.textContent = `
            @keyframes slideInRight { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            @keyframes slideOutRight { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
        `;
        document.head.appendChild(style);
    }
    
    const toast = document.createElement('div');
    const colors = {
        success: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
        error: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        info: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        warning: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
    };
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle',
        warning: 'fa-triangle-exclamation'
    }

    toast.style.cssText = `
        position: fixed; top: 20px; right: 20px;
        background: ${colors[type] || colors['info']};
        color: white; padding: 16px 24px; border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        z-index: 10001; font-weight: 600; display: flex;
        align-items: center; gap: 12px;
        animation: slideInRight 0.4s ease-out forwards;
    `;
    toast.innerHTML = `<i class="fa-solid ${icons[type] || icons['info']}" style="font-size: 1.2rem;"></i><span>${message}</span>`;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.4s ease-out forwards';
        setTimeout(() => toast.remove(), 400);
    }, 3500);
}