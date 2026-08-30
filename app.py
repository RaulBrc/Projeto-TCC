from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==============================================================================
# CONFIGURAÇÕES DE SEGURANÇA E BANCO DE DADOS LOCAL (TCC)
# ==============================================================================
app.config['SECRET_KEY'] = 'chave_secreta_para_o_trituno_2026'
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'instance', 'trituno.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==============================================================================
# MODELOS DO BANCO DE DADOS (trituno.db)
# ==============================================================================

class Usuario(db.Model):
    # 🔥 O ID É STRING: Ele vai guardar exatamente o "UID do usuário" do Firebase!
    id = db.Column(db.String(128), primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    xp = db.Column(db.Integer, default=0)
    diamantes = db.Column(db.Integer, default=0)
    vidas = db.Column(db.Integer, default=5)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    ultima_restauracao_vidas = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

class Licao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modulo = db.Column(db.Integer, nullable=False) 
    titulo = db.Column(db.String(100), nullable=False) 
    conteudo = db.Column(db.Text, nullable=False)  

class Progresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # 🔥 VINCULO DIRETO: Amarra o progresso ao UID String do usuário logado
    usuario_id = db.Column(db.String(128), db.ForeignKey('usuario.id'), nullable=False)
    licao_id = db.Column(db.Integer, db.ForeignKey('licao.id'), nullable=False)
    concluido = db.Column(db.Boolean, default=True)

# ==============================================================================
# PARTE 2: FUNÇÕES DE SUPORTE E SINCRONIZAÇÃO DO FIREBASE
# ==============================================================================

def sincronizar_vidas_usuario(usuario):
    if not usuario:
        return None

    agora = datetime.utcnow()

    if usuario.bloqueado_ate and usuario.bloqueado_ate <= agora:
        usuario.bloqueado_ate = None
        usuario.vidas = 5

    if not usuario.ultima_restauracao_vidas:
        usuario.ultima_restauracao_vidas = agora

    while usuario.vidas < 5 and agora >= usuario.ultima_restauracao_vidas + timedelta(minutes=20):
        usuario.vidas += 1
        usuario.ultima_restauracao_vidas += timedelta(minutes=20)

    if usuario.vidas > 5:
        usuario.vidas = 5

    db.session.commit()
    return usuario


def obter_usuario_sessao():
    """
    Busca no trituno.db o usuário correspondente ao UID do Firebase 
    que está salvo na sessão do navegador do Flask.
    """
    uid_logado = session.get('usuario_id')
    if not uid_logado:
        return None

    usuario = Usuario.query.get(uid_logado)
    return sincronizar_vidas_usuario(usuario)


def calcular_barra_progresso(usuario):
    """
    Faz a regra de três real com base nas lições concluídas por este UID específico.
    Se a tabela Licao estiver vazia no início, usa 5 como padrão (evita Erro 500).
    """
    total_licoes = Licao.query.count()
    if total_licoes == 0: 
        total_licoes = 5  
        
    licoes_concluidas = Progresso.query.filter_by(usuario_id=usuario.id, concluido=True).count()
    return min(int((licoes_concluidas / total_licoes) * 100), 100)


@app.route('/api/salvar-usuario-firebase', methods=['POST'])
def salvar_usuario_firebase():
    """
    O CORAÇÃO DO INTERCÂMBIO:
    Essa rota recebe o UID e o Email do Firebase logo após o login acontecer.
    Se o usuário não existir no trituno.db, cria na hora. Se já existir, sincroniza.
    """
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"status": "erro", "mensagem": "JSON inválido"}), 400

    uid = dados.get('uid')       # O código alfanumérico longo do painel do Firebase
    email = dados.get('email')   # O e-mail do usuário logado (ex: raulz@gmail.com)
    nome = dados.get('nome') or "Músico Aprendiz"

    if not uid or not email:
        return jsonify({"status": "erro", "mensagem": "Dados obrigatórios ausentes"}), 400

    try:
        # Tenta achar o usuário usando o UID vindo do Firebase como chave de busca
        usuario = Usuario.query.get(uid)
        
        if not usuario:
            # Se é um cadastro novo no Firebase, espelha ele imediatamente no banco local do TCC
            usuario = Usuario(id=uid, nome=nome, email=email, vidas=5, xp=0, diamantes=0)
            db.session.add(usuario)
            db.session.commit()
            logger.info("Usuario %s registrado com sucesso no trituno.db via UID.", email)
        else:
            logger.info("Usuario %s ja tem registro local. Sincronizando sessao.", email)

        # 🔥 ESSENCIAL: Guarda o UID na sessão do Flask para blindar a navegação das páginas
        session['usuario_id'] = uid
        return jsonify({"status": "sucesso", "mensagem": "Usuário local sincronizado com Firebase"}), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("Falha ao sincronizar com banco local")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    
    # ==============================================================================
# PARTE 3: ROTAS DE NAVEGAÇÃO (BARRINHA SINCRO-REAL EM TODAS AS TELAS)
# ==============================================================================

@app.route('/')
def pagina_home():
    return render_template('index.html')


@app.route('/login')
def pagina_login():
    return render_template('meu-projeto/login.html')


@app.route('/registro')
def pagina_registro():
    return render_template('meu-projeto/registro.html')


@app.route('/licoes')
def pagina_licoes():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    # Busca a porcentagem unificada baseada no UID do Firebase
    progresso = calcular_barra_progresso(usuario)
    return render_template('meu-projeto/licoes.html', usuario=usuario, progresso=progresso)

@app.route('/introducao')
def pagina_introducao():
    # 1. Mantém a trava de segurança: se não tiver logado, vai pro login
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    # 2. Renderiza o HTML puro, sem forçar variáveis que ele não usa
    return render_template('modulo1/introducao.html')

@app.route('/exercicio1')
def pagina_exercicio1():
    # Trava de segurança para garantir que o usuário está logado
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    # Renderiza o HTML do exercício que está dentro da pasta modulo1
    return render_template('modulo1/exercicio1.html')

@app.route('/loja')
def pagina_loja():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    progresso = calcular_barra_progresso(usuario)
    return render_template('meu-projeto/loja.html', usuario=usuario, progresso=progresso)


@app.route('/ranking')
def pagina_ranking():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    progresso = calcular_barra_progresso(usuario)
    return render_template('meu-projeto/ranking.html', usuario=usuario, progresso=progresso)


@app.route('/configuracoes')
def pagina_configuracoes():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    progresso = calcular_barra_progresso(usuario)
    return render_template('meu-projeto/configuracoes.html', usuario=usuario, progresso=progresso)

# ==============================================================================
# PARTE 4: ROTAS DE JOGO (PROGRESSO/VIDAS) E INICIALIZAÇÃO DO SERVIDOR
# ==============================================================================

@app.route('/api/concluir-licao', methods=['POST'])
def concluir_licao():
    """
    Salva a conclusão da lição associada ao UID do Firebase do usuário.
    Garante que não haverá duplicados e adiciona 10 de XP ao usuário local.
    """
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({"status": "erro", "mensagem": "Usuário não autenticado"}), 401

    dados = request.get_json()
    licao_id = dados.get('licao_id') if dados else 1

    try:
        ja_concluida = Progresso.query.filter_by(usuario_id=usuario.id, licao_id=licao_id).first()

        if not ja_concluida:
            novo_progresso = Progresso(usuario_id=usuario.id, licao_id=licao_id, concluido=True)
            db.session.add(novo_progresso)
            usuario.xp += 10
            db.session.commit()
            logger.info("Licao %s computada para o UID: %s", licao_id, usuario.id)
            return jsonify({
                "status": "sucesso",
                "mensagem": "Progresso gravado localmente!",
                "progresso": calcular_barra_progresso(usuario)
            })

        return jsonify({
            "status": "sucesso",
            "mensagem": "Esta lição já havia sido concluída.",
            "progresso": calcular_barra_progresso(usuario)
        })

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao registrar conclusao da licao")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/perder-vida', methods=['POST'])
def perder_vida():
    """
    Reduz uma vida do usuário. Se chegar a 0, gera um bloqueio de 2 horas.
    """
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({"status": "erro", "mensagem": "Usuário não localizado"}), 404

    if usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.utcnow():
        return jsonify({"status": "ja_bloqueado", "vidas_restantes": usuario.vidas}), 400

    if usuario.vidas > 0:
        usuario.vidas -= 1
        usuario.ultima_restauracao_vidas = datetime.utcnow()
        if usuario.vidas == 0:
            usuario.bloqueado_ate = datetime.utcnow() + timedelta(hours=2)
        db.session.commit()
        return jsonify({"status": "sucesso", "vidas_restantes": usuario.vidas}), 200

    return jsonify({"status": "ja_bloqueado", "vidas_restantes": usuario.vidas}), 400


def garantir_colunas_usuario():
    colunas = [coluna['name'] for coluna in db.inspect(db.engine).get_columns('usuario')]
    if 'ultima_restauracao_vidas' not in colunas:
        with db.engine.begin() as conn:
            conn.execute(db.text('ALTER TABLE usuario ADD COLUMN ultima_restauracao_vidas DATETIME'))


with app.app_context():
    db.create_all()
    garantir_colunas_usuario()


# ==============================================================================
# INICIALIZAÇÃO AUTOMÁTICA DO BANCO E DO SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)

    with app.app_context():
        db.create_all()
        garantir_colunas_usuario()

    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)
