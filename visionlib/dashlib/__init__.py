# ---------------------
# DASHLIB
# ---------------------

import mysql.connector
import logging
from config.database import get_db_connection
from flask import jsonify

logger = logging.getLogger(__name__)


# API para obter mapa de vagas
# Referências no programa principal
# @app.route('/api/mapa-vagas/<int:condominio_id>')
# def api_mapa_vagas(condominio_id)
def obter_mapa_vagas(condominio_id):

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)

    # Ler configuração de colunas por linha e limite total de cadcond
    colunasporlinhanomapa = 10
    _limite = 0
    try:
        cursor.execute("SELECT colunas, limite FROM cadcond WHERE idcond = %s LIMIT 1", (condominio_id,))
        resp_q = cursor.fetchone()
        if resp_q:
            colunasporlinhanomapa = resp_q.get('colunas') or 10
            _limite = resp_q.get('limite') or 0
    except mysql.connector.Error:
        pass

    try:
        # Tentar JOIN por seqcond (preferencial); se falhar, tentar por unidade
        try:
            cursor.execute("""
                SELECT vu.unidade, vu.vperm, COALESCE(ve.estacionados, 0) as vocup
                FROM vagasunidades vu
                LEFT JOIN vw_estacionados ve ON ve.idcond = vu.idcond AND ve.seqcond = vu.seqcond
                WHERE vu.idcond = %s
                ORDER BY vu.seqcond
            """, (condominio_id,))
        except mysql.connector.Error:
            cursor.execute("""
                SELECT vu.unidade, vu.vperm, COALESCE(ve.estacionados, 0) as vocup
                FROM vagasunidades vu
                LEFT JOIN vw_estacionados ve ON ve.idcond = vu.idcond AND ve.unidade = vu.unidade
                WHERE vu.idcond = %s
                ORDER BY vu.unidade
            """, (condominio_id,))
        vagas = cursor.fetchall()
        total_unidades = len(vagas)
        total_vagas_permitidas = _limite if _limite > 0 else sum(vaga['vperm'] for vaga in vagas)
        total_ocupadas = sum(vaga['vocup'] for vaga in vagas)
    except mysql.connector.Error as err:
        logger.error(f"Erro ao carregar mapa de vagas do condomínio {condominio_id}: {err}")
        return jsonify({'success': False, 'message': 'Não temos mapa de vagas para este condomínio!'})

    # Contar veículos não cadastrados da tabela semcadastro
    cursor.execute("""
        SELECT COUNT(DISTINCT s.placa) as total
        FROM semcadastro s
        WHERE s.idcond = %s
    """, (condominio_id,))
    total_nao_cadastrados = cursor.fetchone()['total']

    cursor.close()
    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'vagas': vagas,
            'total_unidades': total_unidades,
            'total_ocupadas': total_ocupadas,
            'total_vagas_permitidas': total_vagas_permitidas,
            'total_nao_cadastrados': total_nao_cadastrados,
            'colunas_linha': colunasporlinhanomapa
        }
    })


# API para obter resumo
# Referências no programa principal
# @app.route('/api/resumo')
# def api_resumo()
def obter_resumo():

    logger.debug("obter_resumo chamado")

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()
    try:
        # Contar condomínios
        cursor.execute("SELECT COUNT(*) FROM cadcond")
        total_condominios = cursor.fetchone()[0]

        # Contar movimentações de hoje - CORREÇÃO: Usar timezone brasileiro e consulta mais robusta
        from datetime import datetime, timedelta
        import pytz

        # Usar timezone brasileiro
        brasil_tz = pytz.timezone('America/Sao_Paulo')
        agora_brasil = datetime.now(brasil_tz)
        hoje_brasil = agora_brasil.strftime('%Y-%m-%d')

        # Consulta mais robusta - verificar múltiplas possibilidades
        cursor.execute("""
            SELECT COUNT(*) FROM movcar 
            WHERE (
                DATE(nowpost) = %s OR 
                DATE(CONVERT_TZ(nowpost, '+00:00', '-03:00')) = %s
            )
            AND contav = 1
        """, (hoje_brasil, hoje_brasil))
        movimentacoes_hoje = cursor.fetchone()[0]

        # Se ainda for 0, tentar sem filtro de contav para debug
        if movimentacoes_hoje == 0:
            cursor.execute("""
                SELECT COUNT(*) FROM movcar 
                WHERE (
                    DATE(nowpost) = %s OR 
                    DATE(CONVERT_TZ(nowpost, '+00:00', '-03:00')) = %s
                )
            """, (hoje_brasil, hoje_brasil))
            movimentacoes_hoje = cursor.fetchone()[0]

        # Obter último registro
        cursor.execute("SELECT MAX(nowpost) FROM movcar WHERE contav = 1")
        ultimo_registro = cursor.fetchone()[0]
        if ultimo_registro:
            ultimo_registro = ultimo_registro.strftime('%Y-%m-%d %H:%M:%S')
        else:
            ultimo_registro = "Nenhum registro"

        return jsonify({
            'success': True,
            'total_condominios': total_condominios,
            'movimentacoes_hoje': movimentacoes_hoje,
            'ultimo_registro': ultimo_registro
        })
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao consultar resumo: {err}'})
    finally:
        cursor.close()
        conn.close()
