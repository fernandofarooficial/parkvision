from config.database import get_db_connection
from datetime import datetime


connection = get_db_connection()
cursor = connection.cursor(dictionary=True)

def lista_mov (xplaca, xqtd, xval, xord):
    """
    :param xplaca: placa do veícylo que temos que localizar
    :param xqtd: quantidade de registros, se for igual a zero é para todos
    :param xval: Se for igual a 1. usar contav = 1
    :param xord: ordenação (D) DESC - (A) ASC
    :return: xrst - dicionário com o(s) registros
    """
    query = f"SELECT * FROM movcar WHERE placa = '{xplaca}'"
    if xval == 1:
        query += " AND contav = 1"
    if xord == 'D':
        query += " ORDER BY idmov DESC"
    else:
        query += " ORDER BY idmov ASC"
    if xqtd != 0:
        query += f" LIMIT {xqtd}"
    cursor.execute(query)
    xrst = cursor.fetchall()
    return xrst



def eliminar_duplicatas (xplaca):
    cursor.execute('SELECT * FROM movcar WHERE placa = %s AND contav = %s', (xplaca, 1))
    movimentos = cursor.fetchall()
    primeiro = datetime.now()
    if movimentos:
        for mov in movimentos:
            idmov = mov['idmov']
            deltat = abs(primeiro - mov['nowpost']).total_seconds()
            if deltat < 180:
                print(f'Nowpost: {mov['nowpost']} ignorado!')
                cursor.execute('UPDATE movcar SET contav = %s WHERE idmov = %s', (0, idmov))
                connection.commit()
            else:
                print(f'Nowpost: {mov['nowpost']} validado!')
                primeiro = mov['nowpost']


while True:
    print('-'*60)
    print('-' * 60)
    print('Gestão da Base Dados ParkVision\n')
    print('1: Eliminar movimentos duplicados no movcar')
    print('2: Incluir carro no Uirapurus')
    print('3: Eliminar veículo do movcar')
    print('4: Exibir veículos de uma unidade')
    print('5: Excluir veículo da base')
    print('6: Eliminar veículo do semcadastro')
    print('7: Alterar placa no movcar')
    print('8: Trocar a direção de um movimento')
    print('0: Fim\n')
    opt = int(input('Opção: '))
    if opt == 0:
        break

    # 01: Eliminar movimentos duplicados no movcar
    if opt == 1:
        placa = input('Informe a placa: ').upper()
        cursor.execute('SELECT * from movcar where placa = %s AND contav = %s', (placa, 1))
        movimentos = cursor.fetchall()
        primeiro = datetime.now()
        if movimentos:
            for mov in movimentos:
                idmov = mov['idmov']
                deltat = abs(primeiro - mov['nowpost']).total_seconds()
                if deltat < 180:
                    print(f'Nowpost: {mov['nowpost']} ignorado!')
                    cursor.execute('UPDATE movcar SET contav = %s WHERE idmov = %s', (0, idmov))
                    connection.commit()
                else:
                    print(f'Nowpost: {mov['nowpost']} validado!')
                    primeiro = mov['nowpost']

    # 02: Incluir carro no Uirapurus
    if opt == 2:
        placa = input('Informe a placa: ').upper()
        # verifica se existe no cadveiculo
        cursor.execute('SELECT placa FROM cadveiculo WHERE placa = %s',(placa,))
        result = cursor.fetchone()
        if result is not None:
            print(f'Placa {placa} já cadastrada da base de dados!')
        else:
            cursor.execute('INSERT INTO cadveiculo (placa, idmodelo, idcor) VALUES (%s, 266, 17);',(placa,))
            connection.commit()
            print(f'Placa {placa} inserida no cadastro de veículos')
        # Verificar se precisa ajustar a direção
        resp = input('Ajusta a direção (S/N)? ').upper()
        if resp == 'N':
            print('Direção não será verificada!')
        else:
            result = lista_mov(placa, 0, 0, "A")
            # cursor.execute('SELECT * FROM movcar WHERE PLACA = %s',(placa,))
            # result = cursor.fetchall()
            if result is None:
                print(f'Não foram encontrados movimentos para a placa {placa}')
            else:
                for rst in result:
                    idmov = rst['idmov']
                    if rst['direcao'] == 'I' and rst['contav'] == 1:
                        print(f'Momento: {rst["nowpost"]}')
                        newdir = input('Nova direção (E/S) ? ').upper()
                        cursor.execute('UPDATE movcar set direcao = %s WHERE idmov = %s2',(newdir,idmov))
                        connection.commit()
                eliminar_duplicatas(placa)


    # 03: Eliminar veículo do movcar
    if opt == 3:
        placa = input('Informe a placa: ').upper()
        # Eliminar co cadcar
        cursor.execute('DELETE FROM movcar WHERE placa = %s',(placa,))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do movcar!')
        else:
            print(f'Placa {placa} não foi excluída do movcar')

    # 4: Exibir veiculos de uma unidade
    if opt == 4:
        cond_id = int(input('Informe código do condomínio: '))
        unid = int(input('Informe a unidade: '))
        cursor.execute('SELECT * FROM cadperm WHERE unidade = %s and idcond = %s',(unid,cond_id))
        rst = cursor.fetchall()
        for i in rst:
            print(i)

    # 05: Excluir veiculo da base
    if opt == 5:
        placa = input('Informe a placa do veículo que será excluído: ').upper()
        cond = int(input('Informe o condomínio: '))
        # Excluir do cadperm
        cursor.execute('DELETE FROM cadperm WHERE idcond = %s AND placa = %s', (cond, placa))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do cadperm!')
        else:
            print(f'Placa {placa} não foi excluída do cadperm!')
        # Excluir do cadveiculo
        cursor.execute('DELETE FROM cadveiculo WHERE placa = %s',(placa,))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do cadveiculo!')
        else:
            print(f'Placa {placa} não foi excluída do cadveiculo!')
        # Excluir do semcadastro
        cursor.execute('DELETE FROM semcadastro WHERE placa = %s',(placa,))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do semcadastro!')
        else:
            print(f'Placa {placa} não foi excluída do semcadastro!')
        # finalizar
        print('Processo de exclusão concluído!!!')

    # 06: Eliminar veículo do semcadastro
    if opt == 6:
        placa = input('Informe a placa do veículo para exclusão do semcadastro: ').upper()
        cursor.execute('DELETE FROM semcadastro WHERE placa = %s', (placa,))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do semcadastro!')
        else:
            print(f'Placa {placa} não foi excluída do semcadastro!')

    # 07: Alterar placa no movcar
    if opt == 7:
        placa_de = input('Informe a placa DE: ').upper()
        placa_para = input('Informe a placa PARA: ').upper()
        # Alterar no movcar
        alterado = False
        cursor.execute('UPDATE movcar set placa = %s WHERE placa = %s', (placa_para, placa_de))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            alterado = True
            print(f'De placa {placa_de} para placa {placa_para} concluído com sucesso do movcar!')
        else:
            print('O DE-PARA NÃO concluído no movcar!')
        # Agora eliminar a placa DE da tabela semcadastro
        cursor.execute("DELETE FROM semcadastro WHERE placa = %s",(placa_de,))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa_de} foi excluída da tabela semcadastro!')
        else:
            print(f'Placa {placa_de} NÃO foi excluída da tabela semcadastro!')
        # incluir no de-para placas
        try:
            cursor.execute('INSERT INTO deparaplacas (placade, placapara) values (%s,%s)', (placa_de, placa_para))
            connection.commit()
            print(f"Commit realizado com sucesso! Placa {placa_de} -> {placa_para} inserida.")
        except Exception as e:
            print(f"Erro ao inserir dados: {e}")

        # eliminar as duplicatas de entrada e saída
        if alterado:
            eliminar_duplicatas(placa_para)

    # 8: Trocar a direção de um movimento'
    if opt == 8:
        placa = input('Informe a placa: ').upper()
        # pegar os movimentos da placa
        movimentos = lista_mov(placa,0,1, 'D')
        qt = 0
        for mov in movimentos:
            qt += 1
        if qt == 0:
            print("Não temos registros para ajuste de direção!")
        else:
            print(f'Temos {qt} registros para ajuste de direção!')
            qt = 0
            for mov in movimentos:
                qt += 1
                newdir = input(f'[{qt}]:: Placa lida: {mov["placalida"]} - Quando: {mov["nowpost"]} - Direção: {mov["direcao"]} - Nova direção (E/S/X): ').upper()
                if newdir in ('X','E','S'):
                    if newdir == 'X':
                        break
                    else:
                        query = f"UPDATE movcar SET direcao = '{newdir}' WHERE idmov = {mov['idmov']}"
                        print(query)
                        cursor.execute(query)
                        connection.commit()
                else:
                    print('Direção inválida! Registro ignorado!')
        eliminar_duplicatas(placa)



print('\nGrato por usar ParkVision!')
cursor.close()
connection.close()