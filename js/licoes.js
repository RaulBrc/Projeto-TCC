// licoes.js

function configurarTrilha() {
    const nodes = document.querySelectorAll('.node');

    nodes.forEach((node, index) => {
        const numeroLicao = index + 1;
        // O nome aqui PRECISA ser igual ao que você salva no exercicio.html
        const licaoId = `trituno_licao_${numeroLicao}`;
        const licaoAnteriorId = `trituno_licao_${index}`;
        
        const estaConcluida = localStorage.getItem(licaoId) === 'concluida';
        const anteriorConcluida = index === 0 || localStorage.getItem(licaoAnteriorId) === 'concluida';

        if (estaConcluida) {
            node.classList.add('done');
            node.classList.remove('locked');
            // Muda o ícone de cadeado para música se já completou
            const icone = node.querySelector('i');
            if (icone) icone.className = 'fa-solid fa-music';
        } else if (anteriorConcluida) {
            node.classList.remove('locked');
            const icone = node.querySelector('i');
            if (icone && icone.classList.contains('fa-lock')) {
                icone.className = 'fa-solid fa-music';
            }
        } else {
            node.classList.add('locked');
        }
    });

    atualizarBarraVisual();
}

function atualizarBarraVisual() {
    const nodes = document.querySelectorAll('.node');
    // Conta quantos botões têm a classe 'done'
    const concluidos = document.querySelectorAll('.node.done').length;
    
    // Cálculo da porcentagem
    const porcentagem = nodes.length > 0 ? Math.round((concluidos / nodes.length) * 100) : 0;

    const fill = document.getElementById('progressFill');
    const text = document.getElementById('progressText');

    if (fill) {
        fill.style.width = porcentagem + "%";
    }
    if (text) {
        text.innerText = porcentagem + "% concluído";
    }
}

// Inicia a configuração assim que a página de trilha carrega
window.onload = configurarTrilha;