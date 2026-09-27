// ==============================================================================
// 1. LÓGICA DE LOGIN (SÓ EXECUTA SE ESTIVER NA PÁGINA DE LOGIN)
// ==============================================================================
const loginForm = document.getElementById('loginForm');

if (loginForm) {
    const passwordInput = document.querySelector('#password');
    const passError = document.getElementById('passError');

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // Bloqueia o recarregamento padrão da página

        const identifierInput = document.querySelector('#email'); // Pode ser e-mail ou nickname
        const identifierValue = identifierInput ? identifierInput.value.trim() : '';
        const passwordValue = passwordInput ? passwordInput.value : '';

        // Validação visual da senha (mínimo de 6 caracteres do Firebase)
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

        try {
            // STEP 1: Resolver E-mail real (caso o usuário tenha digitado o nickname)
            const res = await fetch('/api/obter-email-por-identifier', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier: identifierValue })
            });

            const dataEmail = await res.json();
            
            if (dataEmail.status !== 'sucesso') {
                alert(dataEmail.mensagem || "Usuário não encontrado.");
                return;
            }

            const emailReal = dataEmail.email;

            // STEP 2: Autenticação no Firebase SDK
            if (!window.firebase) {
                console.error("Firebase SDK não foi carregado.");
                return;
            }

            const userCredential = await firebase.auth().signInWithEmailAndPassword(emailReal, passwordValue);
            const user = userCredential.user;

            // STEP 3: Ponte com o Flask - Salva/Sincroniza no trituno.db
            const responseSync = await fetch('/api/salvar-usuario-firebase', {
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

            const dataSync = await responseSync.json();

            if (dataSync.status === "sucesso") {
                console.log("Sincronizado com sucesso com o trituno.db!");
                window.location.href = "/licoes";
            } else {
                alert("Erro na sincronização do banco local: " + dataSync.mensagem);
            }

        } catch (error) {
            console.error("Erro na autenticação:", error);
            alert("Falha no login: Verifique suas credenciais.");
        }
    });
}

// ==============================================================================
// 2. MONITOR DE VIDAS OFFLINE (SÓ EXECUTA FORA DA TELA DE LOGIN/HOME)
// ==============================================================================
function monitorarVidasOffline() {
    // Evita fazer requisições se o usuário estiver em rotas públicas/não autenticadas
    if (['/login', '/registro', '/'].includes(location.pathname)) {
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

// Roda o timer de vidas a cada 1 segundo se não estiver em páginas de auth
if (!['/login', '/registro'].includes(location.pathname)) {
    setInterval(monitorarVidasOffline, 1000);
}