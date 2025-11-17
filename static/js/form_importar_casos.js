// static/js/form_importar_casos.js
function initImportForm(urls) {
    console.log('✅ Formulário de importação carregado!');

    const form = document.getElementById('importForm');
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('arquivo-excel');
    const filePreview = document.getElementById('filePreview');
    const removeFileBtn = document.getElementById('removeFile');
    const submitBtn = document.getElementById('submitBtn');
    const clienteSelect = document.getElementById('cliente-select');
    const produtoSelect = document.getElementById('produto-select');

    if (!form || !uploadArea || !fileInput || !filePreview || !removeFileBtn || !submitBtn) return;

    // --- LÓGICA DE DRAG & DROP E UPLOAD ---
    
    const preventDefaults = (e) => { e.preventDefault(); e.stopPropagation(); };
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => uploadArea.addEventListener(eventName, () => uploadArea.classList.add('dragover')));
    ['dragleave', 'drop'].forEach(eventName => uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('dragover')));

    uploadArea.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });

    uploadArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFile(fileInput.files[0]);
    });

    const handleFile = (file) => {
        if (!file.name.endsWith('.xlsx')) return alert('❌ Apenas arquivos .xlsx são aceitos!');
        if (file.size > 10 * 1024 * 1024) return alert('❌ O arquivo é muito grande! Tamanho máximo: 10MB');

        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = formatFileSize(file.size);
        filePreview.classList.add('visible');
        uploadArea.style.display = 'none';

        // Atualiza o input para que o form o envie
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;

        checkFormValid();
    };

    const formatFileSize = (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
    };

    removeFileBtn.addEventListener('click', () => {
        fileInput.value = '';
        filePreview.classList.remove('visible');
        uploadArea.style.display = 'block';
        checkFormValid();
    });

    // --- VALIDAÇÃO E SUBMIT ---

    const checkFormValid = () => {
        const isValid = clienteSelect.value !== '' && produtoSelect.value !== '' && fileInput.files.length > 0;
        submitBtn.disabled = !isValid;
        submitBtn.style.opacity = isValid ? '1' : '0.6';
        submitBtn.style.cursor = isValid ? 'pointer' : 'not-allowed';
    };

    [clienteSelect, produtoSelect].forEach(el => el.addEventListener('change', checkFormValid));

    form.addEventListener('submit', (e) => {
        if (submitBtn.disabled) {
            e.preventDefault();
            return;
        }
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Importando...';
    });

    console.log('💡 Dicas: Arraste o arquivo .xlsx ou clique para selecionar.');
}