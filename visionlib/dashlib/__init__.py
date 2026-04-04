# ---------------------
# DASHLIB
# ---------------------

import mysql.connector
from config.database import get_db_connection
from flask import jsonify
import globals
from globals import verificar_autenticacao


# API para obter mapa de vagas
# Referências no programa principal
# @app.route('/api/mapa-vagas/<int:condominio_id>')
# def api_mapa_vagas(condominio_id)
def obter_mapa_vagas(condominio_id):

    print("TRACK: Entrei no obter_mapa_vagas")
    
    # Definir numero de colunas por linha
    colunasporlinhanomapa = 10
    for c in globals.cvag:
        if c['idcond'] == condominio_id:
            colunasporlinhanomapa = c['colunas']
            break

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        q = """
        SELECT vu.unidade, vu.vperm, COALESCE(ve.estacionados, 0) as vocup
        FROM vagasunidades vu
        LEFT JOIN vw_estacionados ve ON ve.idcond = vu.idcond AND ve.seqcond = vu.seqcond
        WHERE vu.idcond = %s
        ORDER BY vu.seqcond;
        """
        v = (condominio_id,)
        cursor.execute(q,v)
        vagas = cursor.fetchall()
        total_unidades = len(vagas)
        total_vagas_permitidas = next((item['limite'] for item in globals.cvag if item['idcond'] == condominio_id), 0)
        if total_vagas_permitidas == 0:
            total_vagas_permitidas = sum(vaga['vperm'] for vaga in vagas)
        total_ocupadas = sum(vaga['vocup'] for vaga in vagas)
    except mysql.connector.Error:
        # Se a tabela não existir, encerrar a função
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

    print("TRACK: Entrei no obter_resumo")

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
