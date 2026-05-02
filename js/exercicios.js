// js/exercicios.js

let etapaAtual = 1;
let totalEtapas = 6;
let opcaoCorretaAtiva = false;
let opcaoSelecionada = null;

// Inicializa a lição contando quantas telas existem
window.addEventListener('DOMContentLoaded', () => {
    totalEtapas = document.querySelectorAll('.tela-exercicio').length;
    atualizarBarraInterna();
});

function selecionar(btn, tipo) {
    // Busca a tela onde o usuário clicou
    const telaAtual = btn.closest('.tela-exercicio');
    
    // CORREÇÃO: Remove a seleção de botões OU cards dentro dessa tela
    telaAtual.querySelectorAll('.opcao-btn, .card-opcao').forEach(b => b.classList.remove('selected'));
    
    // Adiciona seleção ao clicado
    btn.classList.add('selected');
    opcaoSelecionada = btn;
    
    // Verifica se é a correta
    opcaoCorretaAtiva = (tipo === 'correta' || btn.id === 'correta');
}

function verificarPasso() {
    if (!opcaoSelecionada) return; // Não faz nada se não selecionou

    const modal = document.getElementById('feedbackModal');
    const msg = document.getElementById('feedbackMsg');
    const icone = document.getElementById('feedbackIcon');

    if (opcaoCorretaAtiva) {
        modal.className = "modal-feedback show correto";
        msg.innerText = "Muito bem!";
        icone.className = "fa-solid fa-circle-check";
    } else {
        modal.className = "modal-feedback show errado";
        msg.innerText = "Resposta incorreta, tente novamente.";
        icone.className = "fa-solid fa-circle-xmark";
    }
}

function proximaAcao() {
    const modal = document.getElementById('feedbackModal');
    modal.classList.remove('show');

    if (opcaoCorretaAtiva) {
        if (etapaAtual < totalEtapas) {
            // Avança para a próxima tela
            document.getElementById(`tela${etapaAtual}`).style.display = 'none';
            etapaAtual++;
            document.getElementById(`tela${etapaAtual}`).style.display = 'block';
            
            // Reseta variáveis para a próxima pergunta
            opcaoCorretaAtiva = false;
            opcaoSelecionada = null;
            atualizarBarraInterna();
        } else {
            // FIM DA LIÇÃO: Salva no localStorage baseado no ID da lição definido no HTML
            const idLicao = document.body.getAttribute('data-licao'); // Pega 'trituno_licao_1'
            localStorage.setItem(idLicao, 'concluida');
            window.location.href = '../meu-projeto/licoes.html'; // Volta para a trilha de lições
        }
    } else {
        // Se errou, apenas desmarca para tentar de novo
        if (opcaoSelecionada) {
            opcaoSelecionada.classList.remove('selected');
            opcaoSelecionada = null;
        }
    }
}

function atualizarBarraInterna() {
    const barra = document.getElementById('barra-interna');
    if (barra) {
        const porcentagem = (etapaAtual / totalEtapas) * 100;
        barra.style.width = porcentagem + "%";
    }
}

function verificar(botao, eCorreto) {
    const todosBotoes = document.querySelectorAll('.option-btn');
    
    // Desativa os botões para não clicar duas vezes
    todosBotoes.forEach(btn => btn.style.pointerEvents = 'none');

    if (eCorreto) {
        botao.classList.add('correct');
        // Aqui você pode tocar um som de "vitoria.mp3"
        // E aumentar a barra de progresso
    } else {
        botao.classList.add('wrong');
        // Som de "erro.mp3"
    }
}