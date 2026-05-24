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

// CORREÇÃO: Adicionado o "async" de volta aqui no começo da função!
async function proximaAcao() {
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
            // ==========================================
            //  FIM DA LIÇÃO: BANCO DE DADOS!
            // ==========================================
            
            const botao = document.getElementById('btnContinuar');
            const licaoId = botao ? botao.getAttribute('data-licao-id') : '1';

            try {
                const resposta = await fetch('/api/concluir-licao', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        licao_id: licaoId
                    })
                });

                const resultado = await resposta.json();
                
                if (resultado.status === 'sucesso') {
                    const aviso = document.getElementById('aviso-recompensa');
                    if (aviso) {
                        aviso.style.display = 'block'; // Mostra o card verde flutuante
                    }

                    // Espera 3 segundos (3000ms) com o aviso na tela antes de redirecionar
                    setTimeout(() => {
                        window.location.href = '/licoes';
                    }, 3000);
                    
                    return; 
                } else {
                    alert("Lição concluída! (Mas houve um erro ao salvar os pontos no servidor).");
                }
            } catch (erro) {
                console.error("Erro ao conectar com o Flask:", erro);
                alert("Lição concluída! (Sem conexão com o servidor para salvar pontos).");
            }

            window.location.href = '/licoes'; 
        }
    } else {
        // ==========================================
        //  O USUÁRIO ERROU A RESPOSTA E FECHOU O MODAL
        // ==========================================
        if (opcaoSelecionada) {
            opcaoSelecionada.classList.remove('selected');
            opcaoSelecionada = null;
        }

        try {
            // Avisa o Flask para tirar uma vida no banco
            const resposta = await fetch('/api/perder-vida', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const resultado = await resposta.json();

            if (resultado.status === 'bloqueado') {
                alert("💔 Você perdeu sua última vida! Você será redirecionado.");
                window.location.href = '/licoes';
                return;
            } else if (resultado.status === 'sucesso') {
                // CORREÇÃO: Altera o texto do contador para o formato Fracionado (ex: 4/5)
                const elementoVidas = document.getElementById('contador-vidas');
                if (elementoVidas) {
                    elementoVidas.innerHTML = `❤️ ${resultado.vidas_restantes}/5`;
                }
            }
        } catch (erro) {
            console.error("Erro ao atualizar vidas no servidor:", erro);
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
    todosBotoes.forEach(btn => btn.style.pointerEvents = 'none');

    if (eCorreto) {
        botao.classList.add('correct');
    } else {
        botao.classList.add('wrong');
    }
}