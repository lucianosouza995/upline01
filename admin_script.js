document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'https://upline01.onrender.com';
    const state = { currentSection: '', editItemId: null, charts: {}, token: localStorage.getItem('upline_token'), cache: {} };

    const ui = {
        loginSection: document.getElementById('login-section'),
        mainPanel: document.getElementById('main-panel'),
        loginForm: document.getElementById('login-form'),
        logoutBtn: document.getElementById('logout-btn'),
        loginError: document.getElementById('login-error'),
        mainNav: document.getElementById('main-nav'),
        contentArea: document.getElementById('content-area'),
        pageTitle: document.getElementById('page-title'),
        formModal: document.getElementById('form-modal'),
        formModalTitle: document.getElementById('form-modal-title'),
        genericForm: document.getElementById('generic-form'),
        spinnerOverlay: document.getElementById('spinner-overlay'),
        toastContainer: document.getElementById('toast-container'),
        confirmationModal: document.getElementById('confirmation-modal'),
        modalText: document.getElementById('modal-text'),
        modalConfirmBtn: document.getElementById('modal-confirm-btn'),
        modalCancelBtn: document.getElementById('modal-cancel-btn'),
    };

    const showSpinner = () => ui.spinnerOverlay.classList.remove('hidden');
    const hideSpinner = () => ui.spinnerOverlay.classList.add('hidden');

    const showToast = (message, type = 'success') => {
        const toast = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-500' : 'bg-red-500';
        toast.className = `text-white px-6 py-3 rounded-md shadow-lg animate-pulse`;
        toast.textContent = message;
        ui.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    const setButtonLoading = (button, isLoading, originalText = '') => {
        const textSpan = button.querySelector('.btn-text');
        const spinner = button.querySelector('.spinner');
        button.disabled = isLoading;
        if (textSpan) textSpan.style.display = isLoading ? 'none' : 'inline';
        if (spinner) spinner.style.display = isLoading ? 'inline-block' : 'none';
        if (!isLoading && textSpan && originalText) textSpan.textContent = originalText;
    };

    const openConfirmationModal = (message, onConfirm) => {
        ui.modalText.textContent = message;
        ui.confirmationModal.classList.remove('hidden');
        ui.modalConfirmBtn.onclick = () => {
            onConfirm();
            ui.confirmationModal.classList.add('hidden');
        };
        ui.modalCancelBtn.onclick = () => ui.confirmationModal.classList.add('hidden');
    };

    const apiRequest = async (endpoint, method = 'GET', body = null) => {
        showSpinner();
        try {
            const options = { method, headers: { 'Content-Type': 'application/json', 'x-access-token': state.token } };
            if (body) options.body = JSON.stringify(body);
            const response = await fetch(`${API_URL}/admin/${endpoint}`, options);
            if (response.status === 401) {
                handleLogout();
                throw new Error('Sessão expirada. Por favor, faça login novamente.');
            }
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Falha na requisição à API' }));
                throw new Error(errorData.message || 'Erro desconhecido');
            }
            if (method !== 'DELETE' && response.status !== 204) return await response.json();
        } finally {
            hideSpinner();
        }
    };
    
    const handleLogout = () => {
        state.token = null;
        state.cache = {};
        localStorage.removeItem('upline_token');
        ui.mainPanel.classList.add('hidden');
        ui.loginSection.classList.remove('hidden');
    };

    const renderTable = (data, rowRenderer) => {
        const tableBody = document.getElementById('data-table-body');
        if (!tableBody) return;
        tableBody.innerHTML = '';
        data.forEach(item => {
            const row = tableBody.insertRow();
            row.innerHTML = rowRenderer(item);
            row.querySelector('.edit-btn')?.addEventListener('click', () => openEditModal(item));
            row.querySelector('.delete-btn')?.addEventListener('click', () => handleDelete(item.id));
        });
    };

    const handleDelete = async (id) => {
        openConfirmationModal(`Tem a certeza que deseja apagar o item #${id}?`, async () => {
            try {
                const singularEndpoint = state.currentSection.slice(0, -1);
                await apiRequest(`${singularEndpoint}/${id}`, 'DELETE');
                showToast('Item apagado com sucesso!', 'success');
                state.cache[state.currentSection] = null;
                await loadSection(`#${state.currentSection}`);
            } catch (error) {
                showToast(`Falha ao apagar o item: ${error.message}`, 'error');
            }
        });
    };
    
    const openEditModal = async (item) => {
        state.editItemId = item.id;
        const section = state.currentSection;
        const handlers = {
            'clientes': () => openClienteModal(item),
            'elevadores': () => openElevadorModal(item),
            'tecnicos': () => openTecnicoModal(item),
        };
        if (handlers[section]) await handlers[section]();
    };
    
    const destroyCharts = () => {
        Object.values(state.charts).forEach(chart => chart.destroy());
        state.charts = {};
    };

    const renderChart = (chartId, type, data, options = {}) => {
        const ctx = document.getElementById(chartId)?.getContext('2d');
        if (!ctx) return;
        if (state.charts[chartId]) state.charts[chartId].destroy();
        state.charts[chartId] = new Chart(ctx, { type, data, options });
    };

    const getCachedData = async (key) => {
        if (state.cache[key]) return state.cache[key];
        const data = await apiRequest(key);
        state.cache[key] = data;
        return data;
    };

    const handleFormSubmit = async (formData, endpointSingular, endpointPlural, loadDataFunction) => {
        const button = ui.genericForm.querySelector('button[type="submit"]');
        setButtonLoading(button, true);
        try {
            const data = Object.fromEntries(formData.entries());
            if (formData.has('possui_contrato')) data.possui_contrato = formData.get('possui_contrato') === 'on';
            
            const method = state.editItemId ? 'PUT' : 'POST';
            const endpoint = state.editItemId ? `${endpointSingular}/${state.editItemId}` : endpointPlural;
            await apiRequest(endpoint, method, data);
            
            state.cache[endpointPlural] = null;
            closeModal();
            showToast(`Registo ${state.editItemId ? 'atualizado' : 'adicionado'} com sucesso!`, 'success');
            await loadDataFunction();
        } catch (error) {
            showToast(`Erro: ${error.message}`, 'error');
        } finally {
            setButtonLoading(button, false, state.editItemId ? 'Guardar Alterações' : 'Adicionar');
        }
    };
    
    const handleClienteSubmit = (formData) => handleFormSubmit(formData, 'cliente', 'clientes', loadClientesData);
    const handleElevadorSubmit = (formData) => handleFormSubmit(formData, 'elevador', 'elevadores', loadElevadoresData);
    const handleTecnicoSubmit = (formData) => handleFormSubmit(formData, 'tecnico', 'tecnicos', loadTecnicosData);

    const loadClientesData = async () => {
        const clientes = await getCachedData('clientes');
        renderTable(clientes, item => `
            <td class="px-6 py-4 whitespace-nowrap">${item.id}</td>
            <td class="px-6 py-4 whitespace-nowrap">${item.nome}</td>
            <td class="px-6 py-4 whitespace-nowrap">${item.possui_contrato ? 'Sim' : 'Não'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button class="edit-btn text-sky-600 hover:text-sky-900">Editar</button>
                <button class="delete-btn text-red-600 hover:text-red-900 ml-4">Apagar</button>
            </td>`);
        document.getElementById('add-btn').onclick = () => openClienteModal();
    };

    const openClienteModal = (item = null) => {
        const isEditing = item !== null;
        const formHtml = `
            <div><label class="block text-sm">Nome do Cliente</label><input name="nome" type="text" value="${isEditing ? item.nome : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div class="flex items-center"><input name="possui_contrato" type="checkbox" ${isEditing && item.possui_contrato ? 'checked' : ''} class="h-4 w-4 rounded"><label class="ml-2">Possui Contrato Ativo</label></div>
            <div class="pt-4 flex justify-end gap-4">
                <button type="button" class="cancel-btn bg-slate-200 px-4 py-2 rounded-lg">Cancelar</button>
                <button type="submit" class="bg-sky-600 text-white px-4 py-2 rounded-lg">${isEditing ? 'Guardar Alterações' : 'Adicionar'}</button>
            </div>`;
        openModal(isEditing ? `Editar Cliente #${item.id}` : 'Adicionar Novo Cliente', formHtml, handleClienteSubmit);
    };

    const loadElevadoresData = async () => {
        const elevadores = await getCachedData('elevadores');
        renderTable(elevadores, item => `
            <td class="px-6 py-4 whitespace-nowrap">${item.codigo_qr}</td>
            <td class="px-6 py-4 whitespace-nowrap">${item.endereco}</td>
            <td class="px-6 py-4 whitespace-nowrap">${item.cliente_nome}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button class="edit-btn text-sky-600 hover:text-sky-900">Editar</button>
                <button class="delete-btn text-red-600 hover:text-red-900 ml-4">Apagar</button>
            </td>`);
        document.getElementById('add-btn').onclick = () => openElevadorModal();
    };

    const openElevadorModal = async (item = null) => {
        const isEditing = item !== null;
        const clientes = await getCachedData('clientes');
        const options = clientes.map(c => `<option value="${c.id}" ${isEditing && c.id === item.cliente_id ? 'selected' : ''}>${c.nome}</option>`).join('');
        const formHtml = `
            <div><label class="block text-sm">Código QR</label><input name="codigo_qr" type="text" value="${isEditing ? item.codigo_qr : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div><label class="block text-sm">Endereço</label><input name="endereco" type="text" value="${isEditing ? item.endereco : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div><label class="block text-sm">Latitude</label><input name="latitude" type="number" step="any" value="${isEditing ? item.latitude : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div><label class="block text-sm">Longitude</label><input name="longitude" type="number" step="any" value="${isEditing ? item.longitude : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div><label class="block text-sm">Cliente</label><select name="cliente_id" required class="mt-1 block w-full border-slate-300 rounded-md">${options}</select></div>
            <div class="pt-4 flex justify-end gap-4">
                <button type="button" class="cancel-btn bg-slate-200 px-4 py-2 rounded-lg">Cancelar</button>
                <button type="submit" class="bg-sky-600 text-white px-4 py-2 rounded-lg">${isEditing ? 'Guardar Alterações' : 'Adicionar'}</button>
            </div>`;
        openModal(isEditing ? `Editar Elevador #${item.id}` : 'Adicionar Novo Elevador', formHtml, handleElevadorSubmit);
    };

    const loadTecnicosData = async () => {
        const tecnicos = await getCachedData('tecnicos');
        renderTable(tecnicos, item => `
            <td class="px-6 py-4 whitespace-nowrap">${item.id}</td>
            <td class="px-6 py-4 whitespace-nowrap">${item.nome}</td>
            <td class="px-6 py-4 whitespace-nowrap">${item.username}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" value="" class="sr-only peer status-toggle" data-id="${item.id}" ${item.de_plantao ? 'checked' : ''}>
                    <div class="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
                    <span class="ml-3 text-sm font-medium text-gray-900">${item.de_plantao ? 'Ativo' : 'Inativo'}</span>
                </label>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button class="edit-btn text-sky-600 hover:text-sky-900">Editar</button>
                <button class="delete-btn text-red-600 hover:text-red-900 ml-4">Apagar</button>
            </td>`);
        document.getElementById('add-btn').onclick = () => openTecnicoModal();
        document.querySelectorAll('.status-toggle').forEach(toggle => {
            toggle.addEventListener('change', handleTecnicoStatusToggle);
        });
    };
    
    const handleTecnicoStatusToggle = async (event) => {
        const toggle = event.target;
        const tecnicoId = toggle.dataset.id;
        const newStatus = toggle.checked;
        try {
            await apiRequest(`tecnico/${tecnicoId}/status`, 'PUT', { de_plantao: newStatus });
            state.cache.tecnicos = null;
            await loadTecnicosData();
            showToast('Status do técnico atualizado!', 'success');
        } catch (error) {
            showToast(`Falha ao alterar o status: ${error.message}`, 'error');
            toggle.checked = !newStatus;
        }
    };

    const openTecnicoModal = (item = null) => {
        const isEditing = item !== null;
        const formHtml = `
            <div><label class="block text-sm">Nome Completo</label><input name="nome" type="text" value="${isEditing ? item.nome : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div><label class="block text-sm">Username (para login)</label><input name="username" type="text" value="${isEditing ? item.username : ''}" required class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div><label class="block text-sm">Senha ${isEditing ? '(deixar em branco para não alterar)' : ''}</label><input name="password" type="password" ${isEditing ? '' : 'required'} class="mt-1 block w-full border-slate-300 rounded-md"></div>
            <div class="pt-4 flex justify-end gap-4">
                <button type="button" class="cancel-btn bg-slate-200 px-4 py-2 rounded-lg">Cancelar</button>
                <button type="submit" class="bg-sky-600 text-white px-4 py-2 rounded-lg">${isEditing ? 'Guardar Alterações' : 'Adicionar'}</button>
            </div>`;
        openModal(isEditing ? `Editar Técnico #${item.id}` : 'Adicionar Novo Técnico', formHtml, handleTecnicoSubmit);
    };

    const loadChamadosData = async (filters = {}) => {
        const queryParams = new URLSearchParams(filters).toString();
        const [chamados, tecnicos, clientes, elevadores] = await Promise.all([
            apiRequest(`chamados?${queryParams}`), getCachedData('tecnicos'),
            getCachedData('clientes'), getCachedData('elevadores')
        ]);

        const populateSelect = (selectId, data, valueField, textField) => {
            const select = document.getElementById(selectId);
            if (!select) return;
            const currentValue = select.value;
            select.innerHTML = '<option value="">Todos</option>';
            data.forEach(item => {
                select.innerHTML += `<option value="${item[valueField]}">${item[textField]}</option>`;
            });
            select.value = currentValue;
        };

        populateSelect('filter-cliente', clientes, 'id', 'nome');
        populateSelect('filter-elevador', elevadores, 'id', 'endereco');
        populateSelect('filter-tecnico', tecnicos, 'id', 'nome');

        const tableBody = document.getElementById('chamados-table-body');
        tableBody.innerHTML = '';
        chamados.forEach(c => {
            const row = tableBody.insertRow();
            let tecnicoCellHtml = c.tecnico_responsavel;
            if (c.status === 'aberto') {
                const techOptions = tecnicos.map(t => `<option value="${t.id}">${t.nome}</option>`).join('');
                tecnicoCellHtml = `
                    <div class="flex items-center gap-2">
                        <select data-chamado-id="${c.id_chamado}" class="assign-tech-select block w-full border-slate-300 rounded-md text-sm">
                            <option value="">Selecione...</option>
                            ${techOptions}
                        </select>
                        <button data-chamado-id="${c.id_chamado}" class="assign-btn bg-sky-500 text-white px-2 py-1 rounded text-xs hover:bg-sky-600">Atribuir</button>
                    </div>`;
            }
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">${c.id_chamado}</td>
                <td class="px-6 py-4 whitespace-nowrap"><span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${c.status === 'finalizado' ? 'bg-green-100 text-green-800' : (c.status === 'atribuido' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800')}">${c.status}</span></td>
                <td class="px-6 py-4 whitespace-nowrap">${c.endereco}</td>
                <td class="px-6 py-4 whitespace-nowrap">${tecnicoCellHtml}</td>
                <td class="px-6 py-4 whitespace-nowrap">${c.data_abertura}</td>`;
        });
        document.querySelectorAll('.assign-btn').forEach(button => button.addEventListener('click', handleManualAssignment));
        
        document.getElementById('apply-filters-btn').onclick = () => {
            const newFilters = {
                data_inicio: document.getElementById('filter-data-inicio').value,
                data_fim: document.getElementById('filter-data-fim').value,
                cliente_id: document.getElementById('filter-cliente').value,
                elevador_id: document.getElementById('filter-elevador').value,
                tecnico_id: document.getElementById('filter-tecnico').value,
            };
            Object.keys(newFilters).forEach(key => !newFilters[key] && delete newFilters[key]);
            loadChamadosData(newFilters);
        };

        document.getElementById('clear-filters-btn').onclick = () => {
            document.getElementById('filters').querySelectorAll('input, select').forEach(el => el.value = '');
            loadChamadosData();
        };
    };

    const handleManualAssignment = async (event) => {
        const button = event.target;
        const chamadoId = button.dataset.chamadoId;
        const select = document.querySelector(`.assign-tech-select[data-chamado-id="${chamadoId}"]`);
        const tecnicoId = select.value;
        if (!tecnicoId) {
            showToast('Por favor, selecione um técnico.', 'error');
            return;
        }
        try {
            await apiRequest(`chamado/${chamadoId}/atribuir`, 'POST', { tecnico_id: tecnicoId });
            showToast('Técnico atribuído com sucesso!', 'success');
            loadChamadosData();
        } catch (error) {
            showToast('Falha ao atribuir técnico.', 'error');
        }
    };
    
    const loadDashboardData = async (filters = {}) => {
        try {
            const queryParams = new URLSearchParams(filters).toString();
            const stats = await apiRequest(`dashboard/stats?${queryParams}`);
            
            const [clientes, elevadores, tecnicos] = await Promise.all([
                getCachedData('clientes'),
                getCachedData('elevadores'),
                getCachedData('tecnicos')
            ]);

            const populateSelect = (selectId, data, valueField, textField) => {
                const select = document.getElementById(selectId);
                if (!select) return;
                const currentValue = select.value;
                select.innerHTML = '<option value="">Todos</option>';
                data.forEach(item => {
                    select.innerHTML += `<option value="${item[valueField]}">${item[textField]}</option>`;
                });
                select.value = currentValue;
            };
            
            populateSelect('filter-cliente', clientes, 'id', 'nome');
            populateSelect('filter-elevador', elevadores, 'id', 'endereco');
            populateSelect('filter-tecnico', tecnicos, 'id', 'nome');

            Object.keys(filters).forEach(key => {
                const filterId = `filter-${key.replace('_id', '')}`;
                const element = document.getElementById(filterId);
                if (element) element.value = filters[key];
            });

            document.getElementById('total-chamados').textContent = stats.total_chamados;
            document.getElementById('total-tecnicos').textContent = stats.total_tecnicos;
            document.getElementById('total-elevadores').textContent = stats.total_elevadores;

            renderChart('statusChart', 'doughnut', {
                labels: Object.keys(stats.chamados_por_status).length > 0 ? Object.keys(stats.chamados_por_status) : ['Nenhum dado'],
                datasets: [{ data: Object.keys(stats.chamados_por_status).length > 0 ? Object.values(stats.chamados_por_status) : [1], backgroundColor: ['#f59e0b', '#22c55e', '#ef4444', '#6b7280'] }]
            }, { responsive: true, maintainAspectRatio: false });

            renderChart('tecnicoChart', 'bar', {
                labels: Object.keys(stats.chamados_por_tecnico),
                datasets: [{ label: 'Nº de Chamados', data: Object.values(stats.chamados_por_tecnico), backgroundColor: '#38bdf8' }]
            }, { responsive: true, maintainAspectRatio: false, indexAxis: 'y' });

            renderChart('mesChart', 'line', {
                labels: stats.chamados_por_mes.map(item => item.mes),
                datasets: [{ label: 'Total de Chamados', data: stats.chamados_por_mes.map(item => item.total), borderColor: '#0ea5e9', backgroundColor: 'rgba(14, 165, 233, 0.1)', fill: true, tension: 0.3 }]
            }, { responsive: true, maintainAspectRatio: false });

            document.getElementById('apply-filters-btn').onclick = () => {
                const newFilters = {
                    data_inicio: document.getElementById('filter-data-inicio').value,
                    data_fim: document.getElementById('filter-data-fim').value,
                    cliente_id: document.getElementById('filter-cliente').value,
                    elevador_id: document.getElementById('filter-elevador').value,
                    tecnico_id: document.getElementById('filter-tecnico').value,
                };
                Object.keys(newFilters).forEach(key => !newFilters[key] && delete newFilters[key]);
                loadDashboardData(newFilters);
            };

            document.getElementById('clear-filters-btn').onclick = () => {
                document.getElementById('dashboard-filters').querySelectorAll('input, select').forEach(el => el.value = '');
                loadDashboardData();
            };

        } catch (error) {
            console.error("Falha ao carregar dados do dashboard:", error);
        }
    };

    const loadSection = async (hash) => {
        destroyCharts();
        const section = hash.substring(1) || 'dashboard';
        state.currentSection = section;
        ui.pageTitle.textContent = section.charAt(0).toUpperCase() + section.slice(1);
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
            if(link.getAttribute('href') === `#${section}`) link.classList.add('active');
        });
        const template = document.getElementById(`${section}-template`);
        if (template) {
            ui.contentArea.innerHTML = template.innerHTML;
            const dataLoaders = {
                'dashboard': loadDashboardData, 'chamados': loadChamadosData,
                'clientes': loadClientesData, 'elevadores': loadElevadoresData,
                'tecnicos': loadTecnicosData,
            };
            if (dataLoaders[section]) await dataLoaders[section]();
        } else {
            ui.contentArea.innerHTML = `<p>Secção não encontrada.</p>`;
        }
    };

    const showMainPanel = () => {
        ui.loginSection.classList.add('hidden');
        ui.mainPanel.classList.remove('hidden');
        ui.mainPanel.style.display = 'flex';
        loadSection(window.location.hash || '#dashboard');
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        const button = e.target.querySelector('button[type="submit"]');
        setButtonLoading(button, true);
        ui.loginError.classList.add('hidden');
        try {
            const username = document.getElementById('admin-username').value;
            const password = document.getElementById('admin-password').value;
            const response = await fetch(`${API_URL}/admin/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await response.json();
            if (response.ok) {
                state.token = data.token;
                localStorage.setItem('upline_token', data.token);
                showMainPanel();
            } else {
                throw new Error(data.message || 'Erro ao fazer login.');
            }
        } catch (error) {
            ui.loginError.textContent = error.message;
            ui.loginError.classList.remove('hidden');
        } finally {
            setButtonLoading(button, false, 'Entrar');
        }
    };

    // --- INICIALIZAÇÃO E NAVEGAÇÃO ---
    if (state.token) {
        showMainPanel();
    } else {
        ui.loginSection.classList.remove('hidden');
    }
    
    ui.loginForm.addEventListener('submit', handleLogin);
    ui.logoutBtn.addEventListener('click', handleLogout);
    ui.mainNav.addEventListener('click', (e) => {
        if (e.target.tagName === 'A' && e.target.href) {
            e.preventDefault();
            window.location.hash = new URL(e.target.href).hash;
        }
    });
    window.addEventListener('hashchange', () => loadSection(window.location.hash));
});
</script>
</body>
</html>
