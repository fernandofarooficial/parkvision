from config.database import get_db_connection

# acertar o campo sit em cadlocal de acordo com a última entrada ou saída do carro
# ultimo movimento é uma saída, sit = 0
# ultimo movimento é uma entrada, sit = 1

# abrir a base
connection = get_db_connection()
cursor = connection.cursor(dictionary=True)

# zerar o sit no cadlocaç
cursor.execute('UPDATE cadlocal set sit = 0')
connection.commit()

# Ler todos os carros com movimento ultimo movimento de entrada
cursor.execute("select * from vw_last_mov where direcao = 'E' and idcond = 1")
lista = cursor.fetchall()

contadentro = 0

for carro in lista:
    print(f'\n\ncarro: {carro}')
    # ver se carro existe no cadlocal
    cursor.execute('SELECT * FROM cadlocal WHERE placa = %s AND idcond = %s LIMIT 1', (carro['placa'],carro['idcond']))
    carrolocal = cursor.fetchone()
    if carrolocal is not None:
        print(f'Carro ({carro['placa']}) localizado no cadlocal')
        cursor.execute("UPDATE cadlocal SET sit = 1 WHERE placa = %s AND idcond = %s", (carro['placa'],carro['idcond']))
        connection.commit()
        contadentro += 1
    else:
        print(f'Carro ({carro['placa']}) sem registro encontrado no cadlocal')

cursor.close()
connection.close()

print(f'Foram atualizados {contadentro} registros!')