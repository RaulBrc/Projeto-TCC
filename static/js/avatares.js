const avatarModal = document.getElementById('avatarModal');
const avatarPreviewImage = document.getElementById('user-avatar-image');
const avatarPreviewIcon = document.getElementById('user-avatar-icon');
const avatarFeedback = document.getElementById('avatarFeedback');
const openAvatarPicker = document.getElementById('openAvatarPicker');

function fecharSeletorAvatar() {
    avatarModal.classList.remove('is-open');
    avatarModal.setAttribute('aria-hidden', 'true');
    openAvatarPicker.focus();
}

openAvatarPicker.addEventListener('click', () => {
    avatarModal.classList.add('is-open');
    avatarModal.setAttribute('aria-hidden', 'false');
    avatarFeedback.textContent = '';
    avatarModal.querySelector('.avatar-option')?.focus();
});

document.getElementById('closeAvatarPicker').addEventListener('click', fecharSeletorAvatar);
avatarModal.addEventListener('click', (event) => {
    if (event.target === avatarModal) fecharSeletorAvatar();
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && avatarModal.classList.contains('is-open')) {
        fecharSeletorAvatar();
    }
});

avatarModal.querySelectorAll('.avatar-option').forEach((option) => {
    option.addEventListener('click', async () => {
        option.disabled = true;
        avatarFeedback.textContent = 'Salvando avatar...';
        try {
            const response = await fetch('/api/avatar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tipo: option.dataset.avatarType,
                    valor: option.dataset.avatarValue
                })
            });
            const result = await response.json();
            if (!response.ok || result.status !== 'sucesso') {
                throw new Error(result.mensagem || 'Não foi possível salvar o avatar.');
            }

            if (result.tipo === 'imagem') {
                avatarPreviewImage.src = result.valor;
                avatarPreviewImage.hidden = false;
                avatarPreviewIcon.hidden = true;
            } else {
                avatarPreviewIcon.className = result.valor;
                avatarPreviewIcon.hidden = false;
                avatarPreviewImage.hidden = true;
            }
            avatarModal.querySelector('.is-selected')?.classList.remove('is-selected');
            option.classList.add('is-selected');
            avatarFeedback.textContent = 'Avatar atualizado.';
        } catch (error) {
            avatarFeedback.textContent = error.message || 'Não foi possível salvar o avatar.';
        } finally {
            option.disabled = false;
        }
    });
});