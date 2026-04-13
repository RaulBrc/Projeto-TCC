document.addEventListener('DOMContentLoaded', () => {
    const togglePassword = document.querySelector('#eyeIcon');
    const passwordInput = document.querySelector('#password');
    const loginForm = document.querySelector('#loginForm');
    const passError = document.querySelector('#passError');

    // Função para mostrar/esconder senha
    togglePassword.addEventListener('click', () => {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        
        // Troca o ícone
        togglePassword.classList.toggle('fa-eye');
        togglePassword.classList.toggle('fa-eye-slash');
    });

    // Validação de formulário
    loginForm.addEventListener('submit', (e) => {
        const passwordValue = passwordInput.value;

        if (passwordValue.length < 8) {
            e.preventDefault(); // Impede o envio
            passError.style.display = 'block';
            passwordInput.style.borderColor = 'var(--error)';
            
            // Pequena animação de "shake" (balanço) no input
            passwordInput.animate([
                { transform: 'translateX(0px)' },
                { transform: 'translateX(5px)' },
                { transform: 'translateX(-5px)' },
                { transform: 'translateX(0px)' }
            ], { duration: 200 });
        } else {
            passError.style.display = 'none';
            passwordInput.style.borderColor = 'var(--primary)';
        }
    });

    // Resetar erro ao digitar
    passwordInput.addEventListener('input', () => {
        if (passwordInput.value.length >= 8) {
            passError.style.display = 'none';
            passwordInput.style.borderColor = 'var(--primary)';
        }
    });
});