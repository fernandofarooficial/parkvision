from config.database import get_db_connection


connection = get_db_connection()
cursor = connection.cursor()

while True:
    print('-'*60)
    print('-' * 60)
    print('Gestão da Base Dados ParkVision\n')
    print('1: Aumentar/diminuir vagas ocupadas em vagasunidades')
    print('2: Alterar sit em cadlocal')
    print('3: Eliminar veículo do movcar')
    print('4: Exibir veículos de uma unidade')
    print('5: Excluir veículo da base')
    print('6: Eliminar veículo do semcadastro')
    print('7: Alterar placa no movcar')
    print('0: Fim\n')
    opt = int(input('Opção: '))
    if opt == 0:
        break

    # 01: Aumentar/diminuir vagas ocupadas em vagasunidades
    if opt == 1:
        unid = input('\nInforme a unidade: ')
        while True:
            oper = int(input('0: Diminuir uma vaga e 1: Aumentar uma vaga:'))
            if oper in (0,1):
                print('Opção válida!')
                break
            else:
                print('Opção inválida!')
        cursor.execute("SELECT vocup from vagasunidades where unidade = %s",(unid,))
        lres = cursor.fetchone()
        valor = lres[0]
        print(f'Valor Antes: {valor}')
        if oper == 0:
            if valor > 0:
                valor -= 1
        else:
            valor += 1
        print(f'Valor Depois: {valor}')
        cursor.execute('UPDATE vagasunidades set vocup = %s where idcond = 1 and unidade = %s',(valor,unid))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print('Registro atualizado com sucesso!')
        else:
            print('Registro não foi atualizado!')

    # 02: Alterar sit em cadlocal
    if opt == 2:
        placa = input('\nInforme a placa: ')
        while True:
            oper = int(input('0: Saída e 1: Entrada:'))
            if oper in (0,1):
                print('Opção válida!')
                break
            else:
                print('Opção inválida!')
        cursor.execute('UPDATE cadlocal set sit = %s where idcond = 1 and placa = %s',(oper,placa))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print('Registro atualizado com sucesso!')
        else:
            print('Registro não foi atualizado!')

    # 03: Eliminar veículo do movcar
    if opt == 3:
        placa = input('Informe a placa: ')
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
        unid = int(input('Informe a unidade: '))
        cursor.execute('SELECT * FROM cadperm WHERE unidade = %s and idcond = %s',(unid,1))
        rst = cursor.fetchall()
        for i in rst:
            print(i)

    # 05: Excluir veiculo da base
    if opt == 5:
        placa = input('Informe a placa do veículo que será excluído: ')
        cond = int(input('Informe o condomínio: '))
        # Excluir do cadperm
        cursor.execute('DELETE FROM cadperm WHERE idcond = %s AND placa = %s', (cond, placa))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do cadperm!')
        else:
            print(f'Placa {placa} não foi excluída do cadperm!')
        # Excluir do cadlocal
        cursor.execute('DELETE FROM cadlocal WHERE idcond = %s and placa = %s', (cond,placa))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do cadlocal!')
        else:
            print(f'Placa {placa} não foi excluída do cadlocal!')
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
        placa = input('Informe a placa do veículo para exclusão do semcadastro: ')
        cursor.execute('DELETE FROM semcadastro WHERE placa = %s', (placa,))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            print(f'Placa {placa} excluída com sucesso do semcadastro!')
        else:
            print(f'Placa {placa} não foi excluída do semcadastro!')

    # 07: Alterar placa no movcar
    if opt == 7:
        placa_de = input('Informe a placa DE: ')
        placa_para = input('Informe a placa PARA: ')
        # Eliminar co cadcar
        cursor.execute('UPDATE movcar set placa = %s WHERE placa = %s', (placa_para, placa_de))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
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
        print('Atividade na tabela movcar concluída!')

print('\nGrato por usar ParkVision!')
cursor.close()
connection.close()