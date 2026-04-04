# ---------------------
# VIEWLIB
# ---------------------

from config.database import get_db_connection

def estacionados_mapa(id_cond):
    """
    :param id_cond: id do condominio
    :return:

    Se for do condominio 1, conta a partir de 6/11
    """
    if id_cond == 1:
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