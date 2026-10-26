from sqlalchemy import text
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import logging
import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==============================================================================
# CONFIGURAÇÕES DE SEGURANÇA E BANCO DE DADOS LOCAL (TCC)
# ==============================================================================
app.config['SECRET_KEY'] = 'chave_secreta_para_o_trituno_2026'
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'instance', 'trituno.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'trituno')
FIREBASE_WEB_API_KEY = os.environ.get(
    'FIREBASE_WEB_API_KEY',
    'AIzaSyBrRC9ZETyyJlQncMkAdfg-kfhf9KfG-uY',
)
db = SQLAlchemy(app)
ultima_sincronizacao_firebase = None

AVATARES_DISPONIVEIS = [
    {"tipo": "icone", "valor": "fa-solid fa-user", "rotulo": "Músico"},
    {"tipo": "icone", "valor": "fa-solid fa-robot", "rotulo": "Robô"},
    {"tipo": "icone", "valor": "fa-solid fa-music", "rotulo": "Nota musical"},
    {"tipo": "imagem", "valor": "/static/images/Trituno_logo.png", "rotulo": "Trituno"},
    {"tipo": "imagem", "valor": "/static/images/Logo_tritunoNovo.png", "rotulo": "Mascote Trituno"},
]
AVATARES_DESBLOQUEADOS_PADRAO = [
    f"{avatar['tipo']}:{avatar['valor']}" for avatar in AVATARES_DISPONIVEIS
]

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
    vidas_maximas = db.Column(db.Integer, default=5)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    ultima_restauracao_vidas = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    avatar_tipo = db.Column(db.String(10), default='icone')
    avatar_valor = db.Column(db.String(255), default='fa-solid fa-user')
    avatares_desbloqueados = db.Column(db.Text, default='[]')
    itens_json = db.Column(db.Text, default='{}')
    firebase_ativo = db.Column(db.Boolean, default=True, nullable=False)

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
        usuario.vidas = usuario.vidas_maximas or 5

    if not usuario.ultima_restauracao_vidas:
        usuario.ultima_restauracao_vidas = agora

    while usuario.vidas < (usuario.vidas_maximas or 5) and agora >= usuario.ultima_restauracao_vidas + timedelta(minutes=20):
        usuario.vidas += 1
        usuario.ultima_restauracao_vidas += timedelta(minutes=20)

    if usuario.vidas > (usuario.vidas_maximas or 5):
        usuario.vidas = usuario.vidas_maximas or 5

    db.session.commit()
    return usuario


def obter_usuario_sessao():
    uid_logado = session.get('usuario_id')
    if not uid_logado:
        return None

    usuario = Usuario.query.get(uid_logado)
    return sincronizar_vidas_usuario(usuario)


def validar_token_firebase(id_token):
    if not id_token:
        raise ValueError('Token Firebase ausente.')

    url = f'https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}'
    request_firebase = Request(
        url,
        data=json.dumps({'idToken': id_token}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request_firebase, timeout=8) as response:
            dados = json.loads(response.read().decode('utf-8'))
    except HTTPError as erro:
        if erro.code in (400, 401):
            raise ValueError('Token Firebase inválido ou expirado.') from erro
        raise RuntimeError('Firebase não conseguiu validar a sessão.') from erro
    except (URLError, TimeoutError) as erro:
        raise RuntimeError('Serviço de autenticação temporariamente indisponível.') from erro

    usuarios = dados.get('users') or []
    if not usuarios or not usuarios[0].get('localId'):
        raise ValueError('Token Firebase sem usuário válido.')
    return usuarios[0]


def sincronizar_diretorio_firebase():
    global ultima_sincronizacao_firebase
    agora = datetime.utcnow()
    if ultima_sincronizacao_firebase and agora - ultima_sincronizacao_firebase < timedelta(minutes=2):
        return

    try:
        import firebase_admin
        from firebase_admin import auth

        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(options={'projectId': FIREBASE_PROJECT_ID})

        usuarios_firebase = []
        pagina = None
        while True:
            resultado = auth.list_users(max_results=1000, page_token=pagina)
            usuarios_firebase.extend(resultado.users)
            pagina = resultado.next_page_token
            if not pagina:
                break

        Usuario.query.update({Usuario.firebase_ativo: False}, synchronize_session=False)
        for perfil in usuarios_firebase:
            if perfil.disabled:
                continue

            uid = perfil.uid
            email = perfil.email or None
            nome = (perfil.display_name or (email.split('@')[0] if email else '') or f'Músico {uid[:8]}').strip()
            usuario = db.session.get(Usuario, uid)
            email_em_uso = email and Usuario.query.filter(
                Usuario.email == email,
                Usuario.id != uid,
            ).first()
            if email_em_uso:
                logger.warning('E-mail duplicado no banco local para o UID Firebase %s; sincronizando sem e-mail.', uid)
                email = None

            if not usuario:
                nickname_base = nome[:42]
                nickname = nickname_base
                if Usuario.query.filter_by(nickname=nickname).first():
                    nickname = f'{nickname_base[:42]}-{uid[-6:]}'
                usuario = Usuario(
                    id=uid,
                    nome=nome[:100],
                    email=email,
                    nickname=nickname[:50],
                    vidas=5,
                    vidas_maximas=5,
                    xp=0,
                    diamantes=0,
                    avatar_tipo='icone',
                    avatar_valor='fa-solid fa-user',
                    avatares_desbloqueados=json.dumps(AVATARES_DESBLOQUEADOS_PADRAO),
                    itens_json='{}',
                    firebase_ativo=True,
                )
                db.session.add(usuario)
            else:
                usuario.nome = nome[:100]
                usuario.firebase_ativo = True
                if email:
                    usuario.email = email

        db.session.commit()
        ultima_sincronizacao_firebase = agora
    except ImportError:
        ultima_sincronizacao_firebase = agora
        logger.warning('Firebase Admin SDK ausente; ranking usa os usuários sincronizados por login.')
    except Exception:
        db.session.rollback()
        ultima_sincronizacao_firebase = agora
        logger.exception('Não foi possível importar os usuários do Firebase Admin.')

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
            usuario.vidas = usuario.vidas_maximas or 5
            usuario.bloqueado_ate = None
            db.session.commit()
            print(f"🎉 Vidas restauradas automaticamente para o usuário [{usuario.email}]!")
            return True # Vidas foram resetadas
            
    return False # Continua bloqueado ou já tinha vidas


def calcular_barra_progresso(usuario):
    total_licoes = Licao.query.count()
    if total_licoes == 0:
        return 0

    licoes_concluidas = (
        db.session.query(func.count(func.distinct(Progresso.licao_id)))
        .join(Licao, Licao.id == Progresso.licao_id)
        .filter(Progresso.usuario_id == usuario.id, Progresso.concluido.is_(True))
        .scalar()
        or 0
    )
    return min(round((licoes_concluidas / total_licoes) * 100), 100)


def usuario_esta_bloqueado(usuario):
    if usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.now():
        return True
    return False


@app.route('/api/salvar-usuario-firebase', methods=['POST'])
def salvar_usuario_firebase():
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"status": "erro", "mensagem": "JSON inválido"}), 400

    try:
        perfil_firebase = validar_token_firebase(dados.get('id_token'))
    except ValueError as erro:
        return jsonify({"status": "erro", "mensagem": str(erro)}), 401
    except RuntimeError as erro:
        return jsonify({"status": "erro", "mensagem": str(erro)}), 503

    uid = perfil_firebase['localId']
    email = perfil_firebase.get('email')
    nome = (perfil_firebase.get('displayName') or dados.get('nome') or "Músico Aprendiz").strip()
    nickname = (dados.get('nickname') or '').strip()

    nickname_final = nickname or nome
    if len(nickname_final) < 3:
        return jsonify({"status": "erro", "mensagem": "Nickname deve ter pelo menos 3 caracteres."}), 400

    usuario = Usuario.query.get(uid)
    nickname_em_uso = Usuario.query.filter(
        Usuario.nickname == nickname_final,
        Usuario.id != uid,
    ).first()
    if nickname_em_uso:
        if nickname:
            return jsonify({"status": "erro", "mensagem": "Este nickname já está em uso."}), 409
        nickname_final = f'{nickname_final[:42]}-{uid[-6:]}'

    try:
        if not usuario:
            usuario = Usuario(
                id=uid,
                nome=nome,
                email=email,
                nickname=nickname_final,
                vidas=5,
                vidas_maximas=5,
                xp=0,
                diamantes=0,
                avatar_tipo='icone',
                avatar_valor='fa-solid fa-user',
                avatares_desbloqueados=json.dumps(AVATARES_DESBLOQUEADOS_PADRAO),
                itens_json='{}',
                firebase_ativo=True,
            )
            db.session.add(usuario)
            logger.info("Usuario %s registrado com sucesso no trituno.db via UID.", email)
        else:
            usuario.nome = usuario.nome or nome
            usuario.firebase_ativo = True
            if email and not Usuario.query.filter(Usuario.email == email, Usuario.id != uid).first():
                usuario.email = email
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
    return render_template(
        'meu-projeto/licoes.html',
        usuario=usuario,
        progresso=progresso,
        total_licoes=Licao.query.count(),
    )


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
    
    return render_template('modulo1/exercicio1.html', total_licoes=Licao.query.count())


@app.route('/exercicio2')
def pagina_exercicio2():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))

    verificar_e_atualizar_vidas(usuario)
    if usuario.vidas == 0:
        return redirect(url_for('pagina_licoes'))

    return render_template('modulo1/exercicio2.html', total_licoes=Licao.query.count())


@app.route('/exercicio3')
def pagina_exercicio3():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))

    verificar_e_atualizar_vidas(usuario)
    if usuario.vidas == 0:
        return redirect(url_for('pagina_licoes'))

    return render_template('modulo1/exercicio3.html', total_licoes=Licao.query.count())


@app.route('/exercicio4')
def pagina_exercicio4():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))

    verificar_e_atualizar_vidas(usuario)
    if usuario.vidas == 0:
        return redirect(url_for('pagina_licoes'))

    return render_template('modulo1/exercicio4.html', total_licoes=Licao.query.count())


@app.route('/loja')
def pagina_loja():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    progresso = calcular_barra_progresso(usuario)
    inventario = json.loads(usuario.itens_json or '{}')
    return render_template(
        'meu-projeto/loja.html',
        usuario=usuario,
        progresso=progresso,
        inventario=inventario,
    )


@app.route('/ranking')
def pagina_ranking():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    progresso = calcular_barra_progresso(usuario)
    sincronizar_diretorio_firebase()
    ranking = (
        Usuario.query.filter_by(firebase_ativo=True)
        .order_by(Usuario.xp.desc(), Usuario.nickname.asc())
        .all()
    )
    return render_template(
        'meu-projeto/ranking.html',
        usuario=usuario,
        progresso=progresso,
        ranking=ranking,
    )


@app.route('/configuracoes')
def pagina_configuracoes():
    usuario = obter_usuario_sessao()
    if not usuario:
        return redirect(url_for('pagina_login'))
    
    progresso = calcular_barra_progresso(usuario)
    licoes_concluidas = Progresso.query.filter_by(usuario_id=usuario.id, concluido=True).count()
    return render_template(
        'meu-projeto/configuracoes.html',
        usuario=usuario,
        progresso=progresso,
        licoes_concluidas=licoes_concluidas,
        avatares=AVATARES_DISPONIVEIS,
        avatares_desbloqueados=json.loads(usuario.avatares_desbloqueados or '[]'),
    )


@app.route('/api/avatar', methods=['POST'])
def atualizar_avatar():
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({'status': 'erro', 'mensagem': 'Sessão expirada.'}), 401

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({'status': 'erro', 'mensagem': 'Dados inválidos.'}), 400

    tipo = dados.get('tipo')
    valor = dados.get('valor')
    avatar = next(
        (item for item in AVATARES_DISPONIVEIS if item['tipo'] == tipo and item['valor'] == valor),
        None,
    )
    if not avatar:
        return jsonify({'status': 'erro', 'mensagem': 'Avatar inválido.'}), 400

    chave_avatar = f'{tipo}:{valor}'
    avatares_desbloqueados = json.loads(usuario.avatares_desbloqueados or '[]')
    if chave_avatar not in avatares_desbloqueados:
        return jsonify({'status': 'erro', 'mensagem': 'Este avatar ainda não foi desbloqueado.'}), 403

    usuario.avatar_tipo = tipo
    usuario.avatar_valor = valor
    db.session.commit()
    return jsonify({'status': 'sucesso', 'tipo': tipo, 'valor': valor})


@app.route('/api/loja/comprar', methods=['POST'])
def comprar_item_loja():
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({'status': 'erro', 'mensagem': 'Sessão expirada.'}), 401

    dados = request.get_json(silent=True)
    item = dados.get('item') if isinstance(dados, dict) else None
    precos = {'vida': 25, 'protecao_ofensiva': 100, 'coracao_cristal': 750}
    if item not in precos:
        return jsonify({'status': 'erro', 'mensagem': 'Item indisponível.'}), 400
    if usuario.diamantes < precos[item]:
        return jsonify({'status': 'erro', 'mensagem': 'Diamantes insuficientes.'}), 400
    if item == 'vida' and usuario.vidas >= (usuario.vidas_maximas or 5):
        return jsonify({'status': 'erro', 'mensagem': 'Você já está com o máximo de vidas.'}), 400
    if item == 'coracao_cristal' and (usuario.vidas_maximas or 5) >= 10:
        return jsonify({'status': 'erro', 'mensagem': 'O limite máximo de vidas já foi desbloqueado.'}), 400

    try:
        usuario.diamantes -= precos[item]
        inventario = json.loads(usuario.itens_json or '{}')
        if item == 'vida':
            usuario.vidas += 1
        elif item == 'protecao_ofensiva':
            inventario[item] = inventario.get(item, 0) + 1
        elif item == 'coracao_cristal':
            usuario.vidas_maximas = 10
            inventario[item] = True
        usuario.itens_json = json.dumps(inventario)
        db.session.commit()
        return jsonify({
            'status': 'sucesso',
            'mensagem': 'Compra realizada com sucesso.',
            'diamantes': usuario.diamantes,
            'vidas': usuario.vidas,
            'vidas_maximas': usuario.vidas_maximas,
            'inventario': inventario,
        })
    except Exception:
        db.session.rollback()
        logger.exception('Falha ao processar compra do usuário %s', usuario.id)
        return jsonify({'status': 'erro', 'mensagem': 'Não foi possível concluir a compra.'}), 500


@app.route('/api/atualizar-perfil', methods=['POST'])
def atualizar_perfil():
    usuario = obter_usuario_sessao()
    if not usuario:
        return jsonify({'status': 'erro', 'mensagem': 'Sessão expirada. Entre novamente.'}), 401

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({'status': 'erro', 'mensagem': 'Dados inválidos.'}), 400

    nome = (dados.get('nome') or '').strip()
    email = (dados.get('email') or '').strip().lower()
    if not nome or len(nome) > 100:
        return jsonify({'status': 'erro', 'mensagem': 'Informe um nome com até 100 caracteres.'}), 400
    if (
        not email
        or len(email) > 100
        or email.count('@') != 1
        or '.' not in email.rsplit('@', 1)[1]
    ):
        return jsonify({'status': 'erro', 'mensagem': 'Informe um e-mail válido.'}), 400

    email_em_uso = Usuario.query.filter(
        Usuario.email == email,
        Usuario.id != usuario.id,
    ).first()
    if email_em_uso:
        return jsonify({'status': 'erro', 'mensagem': 'Este e-mail já está em uso.'}), 409

    if dados.get('validar') is True:
        return jsonify({'status': 'sucesso'})

    try:
        usuario.nome = nome
        usuario.email = email
        db.session.commit()
        return jsonify({
            'status': 'sucesso',
            'mensagem': 'Dados da conta atualizados.',
            'nome': usuario.nome,
            'email': usuario.email,
        })
    except IntegrityError:
        db.session.rollback()
        return jsonify({'status': 'erro', 'mensagem': 'Este e-mail já está em uso.'}), 409
    except Exception:
        db.session.rollback()
        logger.exception('Falha ao atualizar perfil do usuário %s', usuario.id)
        return jsonify({'status': 'erro', 'mensagem': 'Não foi possível salvar as alterações.'}), 500


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'sucesso'})

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

    return jsonify({
        "bloqueado": False,
        "segundos_restantes": 0,
        "vidas": usuario.vidas,
        "vidas_maximas": usuario.vidas_maximas or 5,
    })

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
        return jsonify({
            "status": "sucesso",
            "vidas_restantes": usuario.vidas,
            "vidas_maximas": usuario.vidas_maximas or 5,
        }), 200

    return jsonify({
        "status": "bloqueado",
        "mensagem": "Usuário sem vidas restantes.",
        "vidas_restantes": 0,
        "vidas_maximas": usuario.vidas_maximas or 5,
    }), 400


def garantir_colunas_usuario():
    colunas = [coluna['name'] for coluna in db.inspect(db.engine).get_columns('usuario')]
    novas_colunas = {
        'nickname': 'VARCHAR(50)',
        'ultima_restauracao_vidas': 'DATETIME',
        'vidas_maximas': 'INTEGER DEFAULT 5',
        'avatar_tipo': "VARCHAR(10) DEFAULT 'icone'",
        'avatar_valor': "VARCHAR(255) DEFAULT 'fa-solid fa-user'",
        'avatares_desbloqueados': 'TEXT',
        'itens_json': 'TEXT',
        'firebase_ativo': 'BOOLEAN DEFAULT 1',
    }
    with db.engine.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas:
                conn.execute(text(f'ALTER TABLE usuario ADD COLUMN {nome} {definicao}'))

    for usuario in Usuario.query.all():
        if not usuario.vidas_maximas:
            usuario.vidas_maximas = 5
        if not usuario.avatar_tipo:
            usuario.avatar_tipo = 'icone'
        if not usuario.avatar_valor:
            usuario.avatar_valor = 'fa-solid fa-user'
        if not usuario.avatares_desbloqueados:
            usuario.avatares_desbloqueados = json.dumps(AVATARES_DESBLOQUEADOS_PADRAO)
        if not usuario.itens_json:
            usuario.itens_json = '{}'
    db.session.commit()


def garantir_licoes_iniciais():
    licoes_iniciais = {
        1: ('As Figuras Musicais', 'Introdução às figuras e pausas'),
        2: ('Exercício 1', 'Primeiros exercícios práticos'),
        3: ('Exercício 2: Colcheias', 'Identificação e valores das colcheias'),
        4: ('Exercício 3: Pausas', 'Identificação e duração das pausas musicais'),
        5: ('Exercício 4: Desafio Final', 'Revisão de figuras, valores e pausas'),
    }

    for licao_id, (titulo, conteudo) in licoes_iniciais.items():
        if not db.session.get(Licao, licao_id):
            db.session.add(Licao(
                id=licao_id,
                modulo=1,
                titulo=titulo,
                conteudo=conteudo,
            ))

    db.session.commit()


with app.app_context():
    db.create_all()
    garantir_colunas_usuario()
    garantir_licoes_iniciais()


# ==============================================================================
# INICIALIZAÇÃO AUTOMÁTICA DO BANCO E DO SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)

    with app.app_context():
        db.create_all()
        garantir_colunas_usuario()
        garantir_licoes_iniciais()

    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)
