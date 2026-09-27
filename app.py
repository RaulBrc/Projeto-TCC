from sqlalchemy.exc import IntegrityError
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timedelta

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
    xp = db.Column(db.Integer, default=0)
    diamantes = db.Column(db.Integer, default=0)
    vidas = db.Column(db.Integer, default=5)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)

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

def obter_usuario_sessao():
    uid_logado = session.get('usuario_id')
    if not uid_logado:
        return None
    return Usuario.query.get(uid_logado)

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
    nome = dados.get('nome') or "Músico Aprendiz"

    if not uid or not email:
        return jsonify({"status": "erro", "mensagem": "Dados obrigatórios ausentes"}), 400

    try:
        usuario = Usuario.query.get(uid)

        if not usuario:
            usuario = Usuario(id=uid, nome=nome, email=email, vidas=5, xp=0, diamantes=0)
            db.session.add(usuario)
            db.session.commit()
            print(f"🆕 Usuário [{email}] registrado com sucesso no trituno.db via UID!")
        else:
            print(f"🔄 Usuário [{email}] já tem registro local. Sincronizando sessão.")

        session['usuario_id'] = uid
        return jsonify({"status": "sucesso", "mensagem": "Usuário local sincronizado com Firebase"}), 200

    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": "E-mail já está em uso por outro usuário."}), 409

    except Exception as e:
        db.session.rollback()
        print(f"💥 Erro na sincronização Firebase: {str(e)}")
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


# ==============================================================================
# PARTE 4: ROTAS DE JOGO (PROGRESSO/VIDAS) E INICIALIZAÇÃO DO SERVIDOR
# ==============================================================================

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
            print(f"🚀 Sucesso: Lição {licao_id} computada para o UID: {usuario.id}")
            return jsonify({
                "status": "sucesso",
                "mensagem": "Progresso gravado localmente!",
                "xp_total": usuario.xp
            })

        return jsonify({"status": "sucesso", "mensagem": "Esta lição já havia sido concluída."})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao concluir lição: {str(e)}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/perder-vida', methods=['POST'])
def perder_vida():
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({"status": "erro", "mensagem": "Usuário não localizado"}), 404

    if usuario.vidas == 0:
        if usuario.bloqueado_ate and usuario.bloqueado_ate < datetime.now():
            usuario.vidas = 5
            usuario.bloqueado_ate = None
            db.session.commit()
            return jsonify({"status": "desbloqueado", "vidas_restantes": usuario.vidas, "bloqueado_ate": None}), 200
        else:
            return jsonify({
                "status": "ja_bloqueado",
                "mensagem": f"Usuário bloqueado até {usuario.bloqueado_ate.strftime('%d/%m/%Y %H:%M')}."
            }), 400

    if usuario.vidas > 0:
        usuario.vidas -= 1
        if usuario.vidas == 0:
            usuario.bloqueado_ate = datetime.now() + timedelta(hours=2)
        db.session.commit()
        return jsonify({"status": "sucesso", "vidas_restantes": usuario.vidas}), 200

    return jsonify({"status": "erro", "mensagem": "Caso inesperado"}), 500


# ==============================================================================
# INICIALIZAÇÃO AUTOMÁTICA DO BANCO E DO SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    # 1. Cria a pasta instance se não existir
    os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)
    
    # 2. Prepara o banco e popula os dados iniciais ANTES de ligar o servidor
    with app.app_context():
        db.create_all()
        
        # Popula as lições iniciais caso a tabela esteja vazia
        if Licao.query.count() == 0:
            licao1 = Licao(id=1, modulo=1, titulo="As Figuras Musicais", conteudo="Introdução às figuras e pausas")
            licao2 = Licao(id=2, modulo=1, titulo="Exercício 1", conteudo="Primeiros exercícios práticos")
            db.session.add_all([licao1, licao2])
            db.session.commit()
            print("🎶 Lições iniciais cadastradas no trituno.db!")

    # 3. Liga o servidor por último
    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)