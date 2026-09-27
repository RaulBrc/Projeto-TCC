from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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
    id = db.Column(db.String(128), primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    nickname = db.Column(db.String(50), unique=True, nullable=True)
    xp = db.Column(db.Integer, default=0)
    diamantes = db.Column(db.Integer, default=0)
    vidas = db.Column(db.Integer, default=5)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    ultima_restauracao_vidas = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

class Apostila(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modulo = db.Column(db.Integer, nullable=False) # Ex: Módulo 1, 2, 3...
    titulo = db.Column(db.String(150), nullable=False)
    conteudo = db.Column(db.Text, nullable=False) # Conteúdo em HTML ou Markdown
    resumo = db.Column(db.String(255), nullable=True)

class Licao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modulo = db.Column(db.Integer, nullable=False) 
    titulo = db.Column(db.String(100), nullable=False) 
    conteudo = db.Column(db.Text, nullable=False)  

class Progresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
    uid_logado = session.get('usuario_id')
    if not uid_logado:
        return None

    usuario = Usuario.query.get(uid_logado)
    return sincronizar_vidas_usuario(usuario)

# ==============================================================================
# LÓGICA DO TIMER OFFLINE E RECUPERAÇÃO DE VIDAS
# ==============================================================================

def verificar_e_atualizar_vidas(usuario):
    """
    Verifica se o tempo de bloqueio já passou.
    Se passou, devolve as 5 vidas automaticamente no trituno.db!
    """
    if usuario.vidas == 0 and usuario.bloqueado_ate:
        agora = datetime.now()
        
        # Se a hora atual já ultrapassou a hora limite do bloqueio
        if agora >= usuario.bloqueado_ate:
            usuario.vidas = 5
            usuario.bloqueado_ate = None
            db.session.commit()
            print(f"🎉 Vidas restauradas automaticamente para o usuário [{usuario.email}]!")
            return True # Vidas foram resetadas
            
    return False # Continua bloqueado ou já tinha vidas


def calcular_barra_progresso(usuario):
    total_licoes = Licao.query.count()
    if total_licoes == 0:
        total_licoes = 5  # Valor padrão até popular a tabela de lições
        
    licoes_concluidas = Progresso.query.filter_by(usuario_id=usuario.id, concluido=True).count()
    return min(int((licoes_concluidas / total_licoes) * 100), 100)


def usuario_esta_bloqueado(usuario):
    if usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.now():
        return True
    return False


@app.route('/api/salvar-usuario-firebase', methods=['POST'])
def salvar_usuario_firebase():
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"status": "erro", "mensagem": "JSON inválido"}), 400

    uid = dados.get('uid')
    email = dados.get('email')
    nome = (dados.get('nome') or "Músico Aprendiz").strip()
    nickname = (dados.get('nickname') or '').strip()

    if not uid or not email:
        return jsonify({"status": "erro", "mensagem": "Dados obrigatórios ausentes"}), 400

    nickname_final = nickname or nome
    if len(nickname_final) < 3:
        return jsonify({"status": "erro", "mensagem": "Nickname deve ter pelo menos 3 caracteres."}), 400

    try:
        usuario = Usuario.query.get(uid)

        if not usuario:
            usuario = Usuario(
                id=uid,
                nome=nome,
                email=email,
                nickname=nickname_final,
                vidas=5,
                xp=0,
                diamantes=0,
            )
            db.session.add(usuario)
            logger.info("Usuario %s registrado com sucesso no trituno.db via UID.", email)
        else:
            usuario.nome = usuario.nome or nome
            usuario.email = usuario.email or email
            if nickname and not usuario.nickname:
                usuario.nickname = nickname_final
            logger.info("Usuario %s ja tem registro local. Sincronizando sessao.", email)

        db.session.commit()
        session['usuario_id'] = uid
        return jsonify({"status": "sucesso", "mensagem": "Usuário local sincronizado com Firebase"}), 200

    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": "E-mail já está em uso por outro usuário."}), 409

    except Exception as e:
        db.session.rollback()
        logger.exception("Falha ao sincronizar com banco local")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ==============================================================================
# PARTE 3: ROTAS DE NAVEGAÇÃO
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
    
    # 🔄 Tenta restaurar as 5 vidas se o tempo de bloqueio offline já passou
    verificar_e_atualizar_vidas(usuario)
    
    progresso = calcular_barra_progresso(usuario)
    return render_template('meu-projeto/licoes.html', usuario=usuario, progresso=progresso)


@app.route('/introducao')
def pagina_introducao():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    return render_template('modulo1/introducao.html')


@app.route('/exercicio1')
def pagina_exercicio1():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    # 🔄 Checa vidas: se o tempo passou ele restaura, se continuar com 0 vidas joga pras lições
    verificar_e_atualizar_vidas(usuario)
    if usuario.vidas == 0:
        return redirect(url_for('pagina_licoes'))
    
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

@app.route('/apostila')
def pagina_apostila():
    usuario = obter_usuario_sessao() 
    if not usuario:
        return redirect(url_for('pagina_login'))

    modulo_atual = getattr(usuario, 'modulo', 1) 

    liberadas = Apostila.query.filter(Apostila.modulo <= modulo_atual).all()
    bloqueadas = Apostila.query.filter(Apostila.modulo > modulo_atual).all()
    progresso = calcular_barra_progresso(usuario)

    return render_template('meu-projeto/apostilas.html', usuario=usuario, progresso=progresso, liberadas=liberadas, bloqueadas=bloqueadas)


@app.route('/apostila1')
def pagina_apostila1():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))

    progresso = calcular_barra_progresso(usuario)
    return render_template('apostilasdl/apostila1.html', progresso=progresso)


@app.route('/apostila/<int:apostila_id>')
def ler_apostila(apostila_id):
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))

    apostila = Apostila.query.get_or_404(apostila_id)
    return render_template('ler_apostila.html', apostila=apostila)


# ==============================================================================
# PARTE 4: ROTAS DE JOGO (PROGRESSO/VIDAS) E INICIALIZAÇÃO DO SERVIDOR
# ==============================================================================

@app.route('/api/obter-email-por-identifier', methods=['POST'])
def obter_email_por_identifier():
    dados = request.get_json()
    identifier = dados.get('identifier', '').strip().lower()

    # Verifica se já é um e-mail ou se é um nickname
    if '@' in identifier:
        return jsonify({'status': 'sucesso', 'email': identifier})

    usuario = Usuario.query.filter_by(nickname=identifier).first()
    if usuario:
        return jsonify({'status': 'sucesso', 'email': usuario.email})
    
    return jsonify({'status': 'erro', 'mensagem': 'Usuário ou e-mail não encontrado.'}), 404

@app.route('/api/tempo-bloqueio', methods=['GET'])
def tempo_bloqueio():
    """
    Rota para o JavaScript da tela consultar quantos segundos faltam para desbloquear.
    """
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    # Força a atualização no banco caso o tempo tenha expirado enquanto ele navega
    verificar_e_atualizar_vidas(usuario)

    if usuario.vidas > 0:
        return jsonify({"bloqueado": False, "segundos_restantes": 0, "vidas": usuario.vidas})

    # Se continuar bloqueado, calcula exatamente quantos segundos faltam
    agora = datetime.now()
    if usuario.bloqueado_ate and usuario.bloqueado_ate > agora:
        segundos_restantes = int((usuario.bloqueado_ate - agora).total_seconds())
        return jsonify({
            "bloqueado": True,
            "segundos_restantes": segundos_restantes,
            "vidas": 0
        })

    return jsonify({"bloqueado": False, "segundos_restantes": 0, "vidas": 5})

@app.route('/api/concluir-licao', methods=['POST'])
def concluir_licao():
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({"status": "erro", "mensagem": "Usuário não autenticado"}), 401

    if usuario_esta_bloqueado(usuario):
        return jsonify({
            "status": "erro",
            "mensagem": f"Usuário bloqueado até {usuario.bloqueado_ate.strftime('%d/%m/%Y %H:%M')}."
        }), 403

    dados = request.get_json()
    licao_id = dados.get('licao_id') if dados else 1

    licao = Licao.query.get(licao_id)
    if not licao:
        return jsonify({"status": "erro", "mensagem": f"Lição {licao_id} não encontrada."}), 400

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
                "progresso": calcular_barra_progresso(usuario),
                "xp_total": usuario.xp
            })

        return jsonify({
            "status": "sucesso",
            "mensagem": "Esta lição já havia sido concluída.",
            "progresso": calcular_barra_progresso(usuario),
            "xp_total": usuario.xp
        })

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao registrar conclusao da licao")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/perder-vida', methods=['POST'])
def perder_vida():
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({"status": "erro", "mensagem": "Usuário não localizado"}), 404

    if usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.utcnow():
        return jsonify({
            "status": "bloqueado",
            "mensagem": f"Usuário bloqueado até {usuario.bloqueado_ate.strftime('%d/%m/%Y %H:%M')}.",
            "vidas_restantes": usuario.vidas
        }), 400

    if usuario.vidas > 0:
        usuario.vidas -= 1
        usuario.ultima_restauracao_vidas = datetime.utcnow()
        if usuario.vidas == 0:
            usuario.bloqueado_ate = datetime.utcnow() + timedelta(hours=2)
        db.session.commit()
        return jsonify({"status": "sucesso", "vidas_restantes": usuario.vidas}), 200

    return jsonify({"status": "bloqueado", "mensagem": "Usuário sem vidas restantes.", "vidas_restantes": 0}), 400


def garantir_colunas_usuario():
    colunas = [coluna['name'] for coluna in db.inspect(db.engine).get_columns('usuario')]
    if 'nickname' not in colunas:
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE usuario ADD COLUMN nickname VARCHAR(50)'))
    if 'ultima_restauracao_vidas' not in colunas:
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE usuario ADD COLUMN ultima_restauracao_vidas DATETIME'))


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

        if Licao.query.count() == 0:
            licao1 = Licao(id=1, modulo=1, titulo="As Figuras Musicais", conteudo="Introdução às figuras e pausas")
            licao2 = Licao(id=2, modulo=1, titulo="Exercício 1", conteudo="Primeiros exercícios práticos")
            db.session.add_all([licao1, licao2])
            db.session.commit()
            logger.info("Lições iniciais cadastradas no trituno.db!")

    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)
