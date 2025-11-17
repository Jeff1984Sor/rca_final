// static/js/workflow_builder.js

function workflowBuilder(initialData) {
    return {
        // --- DATA PASSED FROM DJANGO TEMPLATE ---
        workflowId: initialData.workflowId || null,
        saveUrl: initialData.saveUrl,
        loadUrl: initialData.loadUrl,
        listUrl: initialData.listUrl,
        csrfToken: initialData.csrfToken,

        // --- COMPONENT STATE ---
        workflow: {
            nome: initialData.workflowNome || '',
            cliente: initialData.workflowClienteId || '',
            produto: initialData.workflowProdutoId || '',
            fases: [],
        },
        
        modalFaseAberto: false,
        faseEditando: null, // index da fase sendo editada
        faseTemp: {},
        
        // --- METHODS ---
        init() {
            console.log('🚀 Workflow Builder inicializado!');
            
            if (this.workflowId) {
                this.carregarWorkflowExistente();
            } else {
                this.carregarDraft();
            }

            this.$nextTick(() => this.initSortable());
        },
        
        getFaseVazia() {
            return {
                temp_id: `f_${Date.now()}`,
                nome: '',
                pausar_prazo_automaticamente: false,
                tipo_pausa_padrao: '',
                acoes: [],
            };
        },
        
        getAcaoVazia() {
            return {
                temp_id: `a_${Date.now()}${Math.random()}`,
                titulo: '',
                descricao: '',
                tipo: 'SIMPLES',
                tipo_responsavel: 'INTERNO',
                responsavel_padrao: '',
                nome_responsavel_terceiro: '',
                prazo_dias: 0,
                mudar_status_caso_para: '',
                fase_destino_padrao: '',
                fase_destino_sim: '',
                fase_destino_nao: '',
            };
        },
        
        abrirModalFase(index) {
            if (index !== null) {
                this.faseEditando = index;
                this.faseTemp = JSON.parse(JSON.stringify(this.workflow.fases[index]));
            } else {
                this.faseEditando = null;
                this.faseTemp = this.getFaseVazia();
            }
            this.modalFaseAberto = true;
        },
        
        fecharModalFase() {
            this.modalFaseAberto = false;
            this.faseTemp = {};
        },
        
        salvarFase() {
            if (!this.faseTemp.nome || !this.faseTemp.nome.trim()) {
                alert('Por favor, informe o nome da fase!');
                return;
            }
            
            if (this.faseEditando !== null) {
                this.workflow.fases[this.faseEditando] = { ...this.faseTemp };
            } else {
                this.workflow.fases.push({ ...this.faseTemp });
            }
            
            this.fecharModalFase();
            this.autoSave();
        },
        
        deletarFase(index) {
            if (confirm('Tem certeza que deseja deletar esta fase e todas as suas ações?')) {
                this.workflow.fases.splice(index, 1);
                this.autoSave();
            }
        },
        
        adicionarAcao() {
            if (!this.faseTemp.acoes) this.faseTemp.acoes = [];
            this.faseTemp.acoes.push(this.getAcaoVazia());
        },
        
        deletarAcao(index) {
            this.faseTemp.acoes.splice(index, 1);
        },
        
        get isValid() {
            return this.workflow.nome && this.workflow.cliente && this.workflow.produto && this.workflow.fases.length > 0;
        },
        
        autoSave() {
            if (!this.workflowId) {
                localStorage.setItem(`workflow-draft-${this.workflow.cliente}-${this.workflow.produto}`, JSON.stringify(this.workflow));
                console.log('💾 Draft salvo automaticamente');
            }
        },
        
        carregarDraft() {
            if (this.workflow.cliente && this.workflow.produto) {
                const draft = localStorage.getItem(`workflow-draft-${this.workflow.cliente}-${this.workflow.produto}`);
                if (draft) {
                    try {
                        const parsedDraft = JSON.parse(draft);
                        if (confirm('Encontramos um rascunho para este Cliente/Produto. Deseja recuperá-lo?')) {
                            this.workflow = parsedDraft;
                        }
                    } catch (e) { console.error("Erro ao carregar draft:", e); }
                }
            }
        },
        
        async salvarWorkflow() {
            if (!this.isValid) {
                alert('Por favor, preencha o nome, cliente, produto e adicione pelo menos uma fase.');
                return;
            }

            try {
                const response = await fetch(this.saveUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                    body: JSON.stringify({
                        workflow_id: this.workflowId,
                        nome: this.workflow.nome,
                        cliente: this.workflow.cliente,
                        produto: this.workflow.produto,
                        fases: this.workflow.fases,
                    }),
                });
                const data = await response.json();
                if (response.ok && data.success) {
                    if (!this.workflowId) { localStorage.removeItem(`workflow-draft-${this.workflow.cliente}-${this.workflow.produto}`); }
                    alert('✅ Workflow salvo com sucesso!');
                    window.location.href = this.listUrl;
                } else {
                    alert('❌ Erro ao salvar: ' + (data.error || 'Erro desconhecido.'));
                }
            } catch (error) {
                console.error('Erro de rede:', error);
                alert('❌ Erro de rede ao tentar salvar o workflow.');
            }
        },
        
        initSortable() {
            const el = document.getElementById('fases-sortable');
            if (el) {
                Sortable.create(el, {
                    animation: 150,
                    handle: '.fase-numero',
                    onEnd: (evt) => {
                        const movedItem = this.workflow.fases.splice(evt.oldIndex, 1)[0];
                        this.workflow.fases.splice(evt.newIndex, 0, movedItem);
                        this.autoSave();
                    }
                });
            }
        },

        async carregarWorkflowExistente() {
            if (!this.workflowId) return;
            console.log(`Carregando dados do workflow #${this.workflowId}...`);
            try {
                const response = await fetch(this.loadUrl);
                const data = await response.json();
                if (data.success) {
                    this.workflow.nome = data.workflow.nome;
                    this.workflow.cliente = data.workflow.cliente;
                    this.workflow.produto = data.workflow.produto;
                    this.workflow.fases = data.workflow.fases;
                    console.log('✅ Workflow carregado com sucesso!');
                } else {
                    alert('❌ Erro ao carregar dados do workflow: ' + data.error);
                }
            } catch (error) {
                console.error('Erro de rede:', error);
                alert('❌ Erro de rede ao carregar o workflow.');
            }
        },
    };
}