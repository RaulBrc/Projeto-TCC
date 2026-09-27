// ==============================================================================
// 1. LÓGICA DE LOGIN (SÓ EXECUTA SE ESTIVER NA PÁGINA DE LOGIN)
// ==============================================================================
const loginForm = document.getElementById('loginForm');

if (loginForm) {
    const passwordInput = document.querySelector('#password');
    const passError = document.getElementById('passError');

    loginForm.addEventListener('submit', (e) => {
        e.preventDefault(); // Bloqueia o recarregamento padrão da página

        const emailInput = document.querySelector('#email');
        const emailValue = emailInput.value;
        const passwordValue = passwordInput.value;

        // Validação visual da senha (Ajustado para 6 caracteres - padrão Firebase)
        if (passwordValue.length < 6) {
            if (passError) {
                passError.style.display = 'block';
                passError.textContent = "A senha deve ter no mínimo 6 caracteres.";
            }
            passwordInput.style.borderColor = 'var(--error, #ff4b4b)';
            
            passwordInput.animate([
                { transform: 'translateX(0px)' },
                { transform: 'translateX(5px)' },
                { transform: 'translateX(-5px)' },
                { transform: 'translateX(0px)' }
            ], { duration: 200 });
            return;
        } else {
            if (passError) passError.style.display = 'none';
            passwordInput.style.borderColor = 'var(--primary, #58cc02)';
        }

        // CHAMADA AO FIREBASE + FLASK
        // Nota: Se usas Firebase v10 com imports modules, usa o método importado.
        // Se usas a CDN tradicional v8/v9 compat, o código abaixo funciona:
        if (window.firebase) {
            firebase.auth().signInWithEmailAndPassword(emailValue, passwordValue)
                .then((userCredential) => {
                    const user = userCredential.user;

                    // PONTE COM O FLASK: Salva no trituno.db
                    return fetch('/api/salvar-usuario-firebase', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            uid: user.uid,
                            email: user.email,
                            nome: user.displayName || "Músico Aprendiz"
                        })
                    });
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "sucesso") {
                        console.log("Sincronizado com o trituno.db!");
                        window.location.href = "/licoes";
                    } else {
                        alert("Erro na sincronização do banco local: " + data.mensagem);
                    }
                })
                .catch((error) => {
                    console.error("Erro na autenticação:", error.message);
                    alert("Falha no login: Verifique suas credenciais.");
                });
        }
    });
}

// ==============================================================================
// 2. MONITOR DE VIDAS OFFLINE (SÓ EXECUTA FORA DA TELA DE LOGIN/HOME)
// ==============================================================================
function monitorarVidasOffline() {
    // Evita fazer requisições se o usuário estiver na tela de login ou registro
    if (location.pathname === '/login' || location.pathname === '/registro' || location.pathname === '/') {
        return;
    }

    fetch('/api/tempo-bloqueio')
        .then(res => {
            if (!res.ok) throw new Error("Não autenticado");
            return res.json();
        })
        .then(data => {
            if (data.bloqueado) {
                let seg = data.segundos_restantes;
                let h = Math.floor(seg / 3600);
                let m = Math.floor((seg % 3600) / 60);
                let s = seg % 60;
                
                let relogio = 
                    String(h).padStart(2, '0') + ':' +
                    String(m).padStart(2, '0') + ':' +
                    String(s).padStart(2, '0');

                console.log("⏱️ Tempo restante de bloqueio:", relogio);
                
                let elemento = document.getElementById('timer-vidas');
                if (elemento) elemento.textContent = `Novas vidas em: ${relogio}`;
            }
        })
        .catch(err => {
            // Silencia erros de rotas não autenticadas
        });
}

// Roda o timer de vidas a cada 1 segundo se não estiver no login
if (location.pathname !== '/login' && location.pathname !== '/registro') {
    setInterval(monitorarVidasOffline, 1000);
}