// licoes.js

function calcularProgressoLocal() {
    const nodes = document.querySelectorAll('.node');
    if (!nodes.length) return 0;

    let concluidos = 0;
    nodes.forEach((node, index) => {
        const numeroLicao = index + 1;
        const licaoId = `trituno_licao_${numeroLicao}`;
        if (localStorage.getItem(licaoId) === 'concluida') {
            concluidos += 1;
        }
    });

    return Math.min(100, Math.round((concluidos / nodes.length) * 100));
}

function configurarTrilha() {
    const nodes = document.querySelectorAll('.node');

    nodes.forEach((node, index) => {
        const numeroLicao = index + 1;
        const licaoId = `trituno_licao_${numeroLicao}`;
        const licaoAnteriorId = `trituno_licao_${index}`;

        const estaConcluida = localStorage.getItem(licaoId) === 'concluida';
        const anteriorConcluida = index === 0 || localStorage.getItem(licaoAnteriorId) === 'concluida';

        if (estaConcluida) {
            node.classList.add('done');
            node.classList.remove('locked');
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
    const progressoDoServidor = Number(document.body?.dataset?.progresso ?? localStorage.getItem('progress-bar') ?? 0);
    const progressoLocal = calcularProgressoLocal();
    const porcentagem = Number.isFinite(progressoDoServidor) && progressoDoServidor >= 0
        ? Math.max(progressoLocal, progressoDoServidor)
        : progressoLocal;

    const fill = document.getElementById('progressFill');
    const text = document.getElementById('progressText');

    if (fill) {
        fill.style.width = porcentagem + "%";
    }
    if (text) {
        text.innerText = porcentagem + "% concluído";
    }

    localStorage.setItem('progress-bar', String(porcentagem));
}

window.onload = configurarTrilha;