const shopFeedback = document.getElementById('shopFeedback');
const shopBalance = document.getElementById('shopBalance');
const lifeCounter = document.getElementById('contador-vidas');

document.querySelectorAll('[data-shop-item]').forEach((button) => {
    button.addEventListener('click', async () => {
        let comprado = false;
        button.disabled = true;
        shopFeedback.textContent = 'Processando compra...';
        shopFeedback.classList.remove('is-error');
        try {
            const response = await fetch('/api/loja/comprar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item: button.dataset.shopItem })
            });
            const result = await response.json();
            if (!response.ok || result.status !== 'sucesso') {
                throw new Error(result.mensagem || 'Não foi possível concluir a compra.');
            }

            shopBalance.textContent = result.diamantes;
            document.getElementById('contador-diamantes').textContent = result.diamantes;
            lifeCounter.textContent = `${result.vidas}/${result.vidas_maximas}`;
            if (button.dataset.shopItem === 'protecao_ofensiva') {
                document.getElementById('protecaoDisponivel').textContent =
                    `Disponíveis: ${result.inventario.protecao_ofensiva}`;
            }
            if (button.dataset.shopItem === 'coracao_cristal') button.disabled = true;
            comprado = true;
            shopFeedback.textContent = result.mensagem;
        } catch (error) {
            shopFeedback.textContent = error.message || 'Não foi possível concluir a compra.';
            shopFeedback.classList.add('is-error');
        } finally {
            if (button.dataset.shopItem !== 'coracao_cristal' || !comprado) {
                button.disabled = false;
            }
        }
    });
});