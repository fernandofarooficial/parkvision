from config.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

from visionlib.vplib import process_heimdall_plate

placalida = 'EGT8165'
idcond = 2

pulacadastrocarros = False
verifica_placa = process_heimdall_plate(placalida, idcond, 0.8, pulacadastrocarros)

print(f'{verifica_placa}')


cursor.close()
conn.close()


'''



cursor.execute("select * from vagasunidades where idcond = 2")
lista = cursor.fetchall()

for l in lista:
    sq = l['seqcond']
    un = l['unidade']
    ap = un[:3]
    bl = un[4:5]
    nu = f"{ap}_{bl}"
    print(f'un:{un} - Apartamento: {ap} - Bloco: {bl} - Nova Unidade: {nu} - SeqCond: {sq}')
    cursor.execute('update vagasunidades set unidade = %s where seqcond = %s and idcond = 2',(nu,sq))
    conn.commit()





from visionlib.vplib import process_heimdall_plate

placalida = 'EZZ4065'
idcond = 2

pulacadastrocarros = False
verifica_placa = process_heimdall_plate(placalida, idcond, 0.8, pulacadastrocarros)

print(f'{verifica_placa}')
'''

