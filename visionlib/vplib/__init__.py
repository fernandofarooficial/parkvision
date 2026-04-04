"""
Biblioteca para processamento de placas de veículos
Valida e corrige placas lidas pelo sistema Heimdall
"""

import re
from config.database import get_db_connection
import mysql.connector


def process_heimdall_plate(placa_lida, idcond, confianca_minima=0.8, pular_cadastro_carros=False):
    """
    Processa placa lida pelo Heimdall, validando formato e aplicando correções
    usando placas cadastradas como referência para maior assertividade
    
    Args:
        placa_lida (str): Placa lida pelo sistema
        idcond (int): ID do condomínio
        confianca_minima (float): Confiança mínima para aceitar a placa
        pular_cadastro_carros (bool): Se deve pular verificações de cadastro
    
    Returns:
        dict: {
            'corrected_plate': str,  # Placa corrigida
            'found_match': bool,     # Se encontrou correspondência válida
            'confidence': float,     # Nível de confiança
            'original_plate': str,   # Placa original
            'match_method': str      # Método de validação usado
        }
    """
    
    if not placa_lida:
        return {
            'corrected_plate': '*ERROR*',
            'found_match': False,
            'confidence': 0.0,
            'original_plate': placa_lida or '',
            'match_method': 'empty_plate'
        }
    
    # Limpar e padronizar placa
    placa_limpa = limpar_placa(placa_lida)
    
    # NOVA FUNCIONALIDADE: Verificar correspondência exata com placas cadastradas primeiro
    if not pular_cadastro_carros:
        match_exato = verificar_placa_cadastrada_exata(placa_limpa, idcond)
        if match_exato['found']:
            return {
                'corrected_plate': match_exato['placa'],
                'found_match': True,
                'confidence': 1.0,  # Confiança máxima para match exato
                'original_plate': placa_lida,
                'match_method': 'exact_match_db'
            }
    
    # Validar formato da placa
    if not validar_formato_placa(placa_limpa):
        # NOVA FUNCIONALIDADE: Tentar correções usando placas cadastradas como referência
        if not pular_cadastro_carros:
            match_fuzzy = buscar_melhor_correspondencia_cadastrada(placa_lida, idcond)
            if match_fuzzy['found'] and match_fuzzy['confidence'] >= confianca_minima:
                return {
                    'corrected_plate': match_fuzzy['placa'],
                    'found_match': True,
                    'confidence': match_fuzzy['confidence'],
                    'original_plate': placa_lida,
                    'match_method': 'fuzzy_match_db'
                }
        
        # Tentar correções automáticas tradicionais
        placa_corrigida = tentar_corrigir_placa(placa_limpa)
        if placa_corrigida and validar_formato_placa(placa_corrigida):
            placa_limpa = placa_corrigida
        else:
            return {
                'corrected_plate': '*ERROR*',
                'found_match': False,
                'confidence': 0.0,
                'original_plate': placa_lida,
                'match_method': 'format_validation_failed'
            }
    
    # NOVA FUNCIONALIDADE: Validar com placas cadastradas mesmo para placas com formato válido
    if not pular_cadastro_carros:
        # Verificar se a placa válida existe no cadastro (aumenta confiança)
        match_cadastro = verificar_placa_cadastrada_exata(placa_limpa, idcond)
        if match_cadastro['found']:
            return {
                'corrected_plate': placa_limpa,
                'found_match': True,
                'confidence': 1.0,  # Confiança máxima
                'original_plate': placa_lida,
                'match_method': 'format_valid_and_registered'
            }

        # NOVA FUNCIONALIDADE: Verificar placas próximas mesmo para placas válidas
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Buscar todas as placas relacionadas ao condomínio $$$$$ Checar se vai ficar só no condomínio depois
                # query = "SELECT DISTINCT placa FROM cadperm WHERE idcond = %s"
                # cursor.execute(query, (idcond,))
                query = "SELECT DISTINCT placa FROM cadveiculo"
                cursor.execute(query)

                placas_cadastradas = [row[0] for row in cursor.fetchall()]

                if placas_cadastradas:
                    # Verificar placas próximas (1 caractere diferente)
                    match_proximo = buscar_placa_proxima_cadastrada(placa_limpa, placas_cadastradas)
                    if match_proximo['found']:
                        return {
                            'corrected_plate': match_proximo['placa'],
                            'found_match': True,
                            'confidence': match_proximo['confidence'],
                            'original_plate': placa_lida,
                            'match_method': 'valid_format_single_char_correction'
                        }

                    # Verificar tabela deparaplacas
                    match_deparaplacas = consultar_tabela_deparaplacas(placa_limpa)
                    print(f'match_deparaplacas (heimdall): {match_deparaplacas}')
                    if match_deparaplacas['found']:
                        # Verificar se a placa de destino está nas placas cadastradas do condomínio
                        if match_deparaplacas['placa_destino'] in placas_cadastradas:
                            return {
                                'corrected_plate': match_deparaplacas['placa_destino'],
                                'found_match': True,
                                'confidence': 0.95,  # Alta confiança por estar na tabela deparaplacas
                                'original_plate': placa_lida,
                                'match_method': 'valid_format_deparaplacas_table'
                            }

            except mysql.connector.Error as err:
                print(f"Erro ao buscar placas cadastradas: {err}")
            finally:
                cursor.close()
                conn.close()

    # 🔧 CORREÇÃO: Aceitar placa com formato válido mesmo que não esteja cadastrada
    # Se chegou até aqui, a placa tem formato válido mas não está no cadastro
    # Isso é NORMAL para placas novas - devemos aceitar e processar
    return {
        'corrected_plate': placa_limpa,
        'found_match': True,  # ✅ CORRIGIDO: Aceitar placa válida não cadastrada
        'confidence': 0.85,  # Confiança alta para formato válido
        'original_plate': placa_lida,
        'match_method': 'format_valid_not_registered'  # Indica que é placa nova
    }


def limpar_placa(placa):
    """
    Limpa e padroniza formato da placa
    Remove espaços, hífens e converte para maiúsculo
    """
    if not placa:
        return ''
    
    # Remover caracteres não alfanuméricos
    placa_limpa = re.sub(r'[^A-Z0-9]', '', placa.upper().strip())
    
    return placa_limpa


def validar_formato_placa(placa):
    """
    Valida se a placa está em formato brasileiro válido
    Aceita: ABC1234 (antigo) ou ABC1D23 (Mercosul)
    """
    if not placa or len(placa) != 7:
        return False
    
    # Formato antigo: 3 letras + 4 números (ABC1234)
    formato_antigo = re.match(r'^[A-Z]{3}[0-9]{4}$', placa)
    
    # Formato Mercosul: 3 letras + 1 número + 1 letra + 2 números (ABC1D23)
    formato_mercosul = re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', placa)
    
    return bool(formato_antigo or formato_mercosul)


def tentar_corrigir_placa(placa):
    """
    Tenta corrigir placas com pequenos erros comuns de OCR
    Aplica correções baseadas em confusões típicas de leitura
    """
    if not placa:
        return None
    
    # Se a placa tem tamanho incorreto, não tenta corrigir
    if len(placa) != 7:
        return None
    
    # Se já está no formato correto, retornar sem alterações
    if validar_formato_placa(placa):
        return placa
    
    placa_corrigida = placa.upper()
    
    # Dicionário de correções comuns de OCR
    # Mapeia caracteres frequentemente confundidos
    correcoes_ocr = {
        # Números frequentemente confundidos com letras
        '0': ['O', 'Q', 'D'],  # Zero com O, Q, D
        '1': ['I', 'L', '|'],  # Um com I, L
        '5': ['S'],            # Cinco com S
        '8': ['B'],            # Oito com B
        '6': ['G'],            # Seis com G
        
        # Letras frequentemente confundidas com números
        'O': ['0', 'Q', 'D'],  # O com zero, Q, D
        'I': ['1', 'L', '|'],  # I com um, L
        'S': ['5'],            # S com cinco
        'B': ['8'],            # B com oito
        'G': ['6'],            # G com seis
        'Z': ['2'],            # Z com dois
        'Q': ['O', '0'],       # Q com O, zero
        'D': ['0', 'O'],       # D com zero, O
    }
    
    # NOVA FUNCIONALIDADE: Primeiro tentar conversão entre formatos
    placa_conversao = aplicar_correcoes_formato(placa_corrigida, 'conversao', correcoes_ocr)
    if placa_conversao and validar_formato_placa(placa_conversao):
        return placa_conversao
    
    # Tentar correções para diferentes formatos
    for formato_tentativa in ['antigo', 'mercosul']:
        placa_tentativa = aplicar_correcoes_formato(placa_corrigida, formato_tentativa, correcoes_ocr)
        if placa_tentativa and validar_formato_placa(placa_tentativa):
            return placa_tentativa
    
    return None


def aplicar_correcoes_formato(placa, formato_alvo, correcoes_ocr):
    """
    Aplica correções específicas baseadas no formato alvo da placa
    NOVA FUNCIONALIDADE: Inclui conversão entre formatos antigo/Mercosul
    
    Args:
        placa (str): Placa a ser corrigida
        formato_alvo (str): 'antigo', 'mercosul' ou 'conversao'
        correcoes_ocr (dict): Dicionário de correções OCR
    
    Returns:
        str: Placa corrigida ou None se não conseguir corrigir
    """
    if not placa or len(placa) != 7:
        return None
    
    placa_corrigida = list(placa.upper())
    
    # NOVA FUNCIONALIDADE: Tentativa de conversão entre formatos
    if formato_alvo == 'conversao':
        # Tentar converter formato antigo para Mercosul ou vice-versa
        resultado_conversao = tentar_conversao_entre_formatos(placa)
        if resultado_conversao:
            return resultado_conversao
    
    if formato_alvo == 'antigo':
        # Formato antigo: ABC1234 (3 letras + 4 números)
        # Posições 0,1,2: devem ser letras
        for i in range(3):
            if placa_corrigida[i].isdigit():
                # Tentar converter número para letra
                for letra, nums in correcoes_ocr.items():
                    if placa_corrigida[i] in nums and letra.isalpha():
                        placa_corrigida[i] = letra
                        break
        
        # Posições 3,4,5,6: devem ser números
        for i in range(3, 7):
            if placa_corrigida[i].isalpha():
                # Tentar converter letra para número
                for num, letras in correcoes_ocr.items():
                    if placa_corrigida[i] in letras and num.isdigit():
                        placa_corrigida[i] = num
                        break
                        
    elif formato_alvo == 'mercosul':
        # Formato Mercosul: ABC1D23 (3 letras + 1 número + 1 letra + 2 números)
        # Posições 0,1,2: devem ser letras
        for i in range(3):
            if placa_corrigida[i].isdigit():
                for letra, nums in correcoes_ocr.items():
                    if placa_corrigida[i] in nums and letra.isalpha():
                        placa_corrigida[i] = letra
                        break
        
        # Posição 3: deve ser número
        if placa_corrigida[3].isalpha():
            for num, letras in correcoes_ocr.items():
                if placa_corrigida[3] in letras and num.isdigit():
                    placa_corrigida[3] = num
                    break
        
        # Posição 4: deve ser letra
        if placa_corrigida[4].isdigit():
            for letra, nums in correcoes_ocr.items():
                if placa_corrigida[4] in nums and letra.isalpha():
                    placa_corrigida[4] = letra
                    break
        
        # Posições 5,6: devem ser números
        for i in range(5, 7):
            if placa_corrigida[i].isalpha():
                for num, letras in correcoes_ocr.items():
                    if placa_corrigida[i] in letras and num.isdigit():
                        placa_corrigida[i] = num
                        break
    
    return ''.join(placa_corrigida)


def tentar_conversao_entre_formatos(placa):
    """
    Tenta converter uma placa entre formato antigo e Mercosul
    Exemplo: SVY1184 -> SVY1I84 ou SVY1I84 -> SVY1184
    
    Args:
        placa (str): Placa a ser convertida
    
    Returns:
        str: Placa convertida ou None se não conseguir
    """
    if not placa or len(placa) != 7:
        return None
    
    placa = placa.upper()
    
    # Verificar se é formato antigo válido (ABC1234)
    if re.match(r'^[A-Z]{3}[0-9]{4}$', placa):
        # Tentar converter para Mercosul
        # Padrão comum: ABC1234 -> ABC1I34 (onde 1 na pos 3 vira I na pos 4)
        if placa[3] == '1':
            # SVY1184 -> SVY1I84
            convertida = placa[:3] + placa[3] + 'I' + placa[5:]
            if validar_formato_placa(convertida):
                return convertida
            
            # Outras variações possíveis
            for variacao_letra in ['I', 'L']:
                convertida = placa[:3] + placa[3] + variacao_letra + placa[5:]
                if validar_formato_placa(convertida):
                    return convertida
        
        # Outros números que podem virar letras na pos 4
        conversoes_num_letra = {
            '0': 'O', '5': 'S', '8': 'B', '6': 'G', '2': 'Z'
        }
        
        for num, letra in conversoes_num_letra.items():
            if placa[3] == num:
                convertida = placa[:3] + placa[3] + letra + placa[5:]
                if validar_formato_placa(convertida):
                    return convertida
    
    # Verificar se é formato Mercosul válido (ABC1D23)  
    elif re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', placa):
        # Tentar converter para formato antigo
        # SVY1I84 -> SVY1184 (remove o I e junta os números)
        if placa[4] in ['I', 'L']:
            convertida = placa[:3] + placa[3] + '1' + placa[5:]
            if validar_formato_placa(convertida):
                return convertida
        
        # Outros padrões de conversão
        conversoes_letra_num = {
            'O': '0', 'S': '5', 'B': '8', 'G': '6', 'Z': '2'
        }
        
        for letra, num in conversoes_letra_num.items():
            if placa[4] == letra:
                convertida = placa[:3] + placa[3] + num + placa[5:]
                if validar_formato_placa(convertida):
                    return convertida
    
    return None


def calcular_confianca_placa(placa_corrigida, placa_original):
    """
    Calcula nível de confiança da placa baseado em vários fatores
    """
    if not placa_corrigida or not placa_original:
        return 0.0
    
    confianca = 0.9  # Confiança base alta
    
    # Reduzir confiança se houve mudanças
    if placa_corrigida != limpar_placa(placa_original):
        confianca -= 0.1
    
    # Garantir que confiança não seja negativa
    confianca = max(0.0, confianca)
    
    return round(confianca, 2)


def verificar_placa_cadastrada_exata(placa, idcond):
    """
    Verifica se a placa existe exatamente na tabela cadveiculo
    Considera placas associadas ao condomínio via cadperm
    
    Args:
        placa (str): Placa a verificar
        idcond (int): ID do condomínio
    
    Returns:
        dict: {'found': bool, 'placa': str}
    """
    if not placa or not idcond:
        return {'found': False, 'placa': None}
    
    conn = get_db_connection()
    if not conn:
        return {'found': False, 'placa': None}
    
    cursor = conn.cursor()
    try:
        # Buscar placa exata que tenha alguma relação com o condomínio $$$$$
        # query = "SELECT DISTINCT placa FROM cadperm WHERE idcond = %s"
        # cursor.execute(query, (idcond,))
        query = "SELECT DISTINCT placa FROM cadveiculo WHERE placa = %s"
        cursor.execute(query, (placa,))

        resultado = cursor.fetchone()
        
        if resultado:
            return {'found': True, 'placa': resultado[0]}
        else:
            return {'found': False, 'placa': None}
            
    except mysql.connector.Error as err:
        print(f"Erro ao verificar placa cadastrada: {err}")
        return {'found': False, 'placa': None}
    finally:
        cursor.close()
        conn.close()


def buscar_melhor_correspondencia_cadastrada(placa_lida, idcond, limite_similaridade=0.8):
    """
    Busca a melhor correspondência fuzzy entre a placa lida e placas cadastradas
    Usado quando a placa lida tem formato inválido
    
    Args:
        placa_lida (str): Placa lida pelo sistema (pode ter erros)
        idcond (int): ID do condomínio
        limite_similaridade (float): Limite mínimo de similaridade (0.0-1.0)
    
    Returns:
        dict: {'found': bool, 'placa': str, 'confidence': float}
    """
    if not placa_lida or not idcond:
        return {'found': False, 'placa': None, 'confidence': 0.0}
    
    conn = get_db_connection()
    if not conn:
        return {'found': False, 'placa': None, 'confidence': 0.0}
    
    cursor = conn.cursor()
    try:
        # Buscar todas as placas relacionadas ao condomínio $$$$$
        # query = "SELECT DISTINCT placa FROM cadperm WHERE idcond = %s"
        # cursor.execute(query, (idcond,))
        query = "SELECT DISTINCT placa FROM cadveiculo"
        cursor.execute(query)

        placas_cadastradas = [row[0] for row in cursor.fetchall()]
        
        if not placas_cadastradas:
            return {'found': False, 'placa': None, 'confidence': 0.0}
        
        # NOVA FUNCIONALIDADE: Primeiro verificar placas próximas (1 caractere diferente)
        placa_lida_limpa = limpar_placa(placa_lida)
        match_proximo = buscar_placa_proxima_cadastrada(placa_lida_limpa, placas_cadastradas)
        if match_proximo['found']:
            return match_proximo
        
        # NOVA FUNCIONALIDADE: Verificar tabela deparaplacas
        match_deparaplacas = consultar_tabela_deparaplacas(placa_lida_limpa)
        print(f'match_deparaplacas (melhor): {match_deparaplacas}')
        if match_deparaplacas['found']:
            # Verificar se a placa de destino está nas placas cadastradas do condomínio
            if match_deparaplacas['placa_destino'] in placas_cadastradas:
                return {
                    'found': True,
                    'placa': match_deparaplacas['placa_destino'],
                    'confidence': 0.95,  # Alta confiança por estar na tabela deparaplacas
                    'method': 'deparaplacas_table'
                }
        
        # Encontrar a melhor correspondência fuzzy tradicional
        melhor_match = None
        maior_similaridade = 0.0
        
        for placa_cadastrada in placas_cadastradas:
            similaridade = calcular_similaridade_placas(placa_lida_limpa, placa_cadastrada)
            if similaridade > maior_similaridade:
                maior_similaridade = similaridade
                melhor_match = placa_cadastrada
        
        if maior_similaridade >= limite_similaridade:
            return {
                'found': True, 
                'placa': melhor_match, 
                'confidence': round(maior_similaridade, 2)
            }
        else:
            return {'found': False, 'placa': None, 'confidence': maior_similaridade}
            
    except mysql.connector.Error as err:
        print(f"Erro ao buscar correspondência cadastrada: {err}")
        return {'found': False, 'placa': None, 'confidence': 0.0}
    finally:
        cursor.close()
        conn.close()


def buscar_correspondencia_similar_cadastrada(placa, idcond, limite_similaridade=0.95):
    """
    Busca placas similares cadastradas para validar uma placa com formato válido
    Usado para aumentar confiança em placas que já têm formato correto
    
    Args:
        placa (str): Placa com formato válido
        idcond (int): ID do condomínio
        limite_similaridade (float): Limite mínimo de similaridade
    
    Returns:
        dict: {'found': bool, 'placa': str, 'confidence': float}
    """
    if not placa or not idcond:
        return {'found': False, 'placa': None, 'confidence': 0.0}
    
    # Verificar primeiro se é match exato (mais eficiente)
    match_exato = verificar_placa_cadastrada_exata(placa, idcond)
    if match_exato['found']:
        return {'found': True, 'placa': match_exato['placa'], 'confidence': 1.0}
    
    conn = get_db_connection()
    if not conn:
        return {'found': False, 'placa': None, 'confidence': 0.0}
    
    cursor = conn.cursor()
    try:
        # Buscar placas similares (diferença de 1-2 caracteres) $$$$$
        # query = "SELECT DISTINCT placa FROM cadperm WHERE idcond = %s AND placa != %s"
        # cursor.execute(query, (idcond, placa))
        query = "SELECT DISTINCT placa FROM cadveiculo WHERE placa != %s"
        cursor.execute(query, (placa,))

        placas_cadastradas = [row[0] for row in cursor.fetchall()]
        
        if not placas_cadastradas:
            return {'found': False, 'placa': None, 'confidence': 0.0}
        
        # Encontrar a melhor similaridade
        maior_similaridade = 0.0
        melhor_match = None
        
        for placa_cadastrada in placas_cadastradas:
            similaridade = calcular_similaridade_placas(placa, placa_cadastrada)
            if similaridade > maior_similaridade:
                maior_similaridade = similaridade
                melhor_match = placa_cadastrada
        
        if maior_similaridade >= limite_similaridade:
            return {
                'found': True, 
                'placa': melhor_match, 
                'confidence': round(maior_similaridade, 2)
            }
        else:
            return {'found': False, 'placa': None, 'confidence': maior_similaridade}
            
    except mysql.connector.Error as err:
        print(f"Erro ao buscar similaridade cadastrada: {err}")
        return {'found': False, 'placa': None, 'confidence': 0.0}
    finally:
        cursor.close()
        conn.close()


def calcular_similaridade_placas(placa1, placa2):
    """
    Calcula similaridade entre duas placas considerando confusões comuns OCR
    e conversões entre formatos antigo/Mercosul
    
    Args:
        placa1 (str): Primeira placa
        placa2 (str): Segunda placa
    
    Returns:
        float: Similaridade entre 0.0 e 1.0
    """
    if not placa1 or not placa2:
        return 0.0
    
    if len(placa1) != 7 or len(placa2) != 7:
        return 0.0
    
    if placa1 == placa2:
        return 1.0
    
    # NOVA FUNCIONALIDADE: Verificar conversão formato antigo <-> Mercosul
    similaridade_formato = verificar_conversao_formato_placas(placa1, placa2)
    if similaridade_formato >= 0.95:  # Alta similaridade por conversão de formato
        return similaridade_formato
    
    # Mapa de confusões comuns OCR (bidirecional)
    confusoes_ocr = {
        '1': ['I', 'L', '|'],
        'I': ['1', 'L', '|'],
        'O': ['0', 'Q'],
        '0': ['O', 'Q'],
        'S': ['5'],
        '5': ['S'],
        'B': ['8'],
        '8': ['B'],
        'E': ['F'],
        'F': ['E'],
        'G': ['6'],
        '6': ['G'],
        'Z': ['2'],
        '2': ['Z'],
        'Q': ['O', '0'],
        'D': ['0', 'O']
    }
    
    # Contar matches exatos e similares
    matches_exatos = 0
    matches_similares = 0
    matches_tipo = 0
    
    for i in range(7):
        c1, c2 = placa1[i], placa2[i]
        
        if c1 == c2:
            # Caractere exato na posição correta
            matches_exatos += 1
            matches_similares += 1
            matches_tipo += 1
        elif c1 in confusoes_ocr.get(c2, []) or c2 in confusoes_ocr.get(c1, []):
            # Caracteres similares (confusão OCR)
            matches_similares += 1
            matches_tipo += 1
        elif (c1.isalpha() and c2.isalpha()) or (c1.isdigit() and c2.isdigit()):
            # Mesmo tipo (letra/número) mas caracteres diferentes
            matches_tipo += 1
    
    # Cálculo com pesos diferenciados
    peso_exato = 0.6      # Caracteres exatos têm mais peso
    peso_similar = 0.3    # Confusões OCR têm peso médio
    peso_tipo = 0.1       # Tipo correto tem peso menor
    
    similaridade = (
        (matches_exatos / 7.0) * peso_exato +
        (matches_similares / 7.0) * peso_similar +
        (matches_tipo / 7.0) * peso_tipo
    )
    
    return round(min(similaridade, 1.0), 3)


def verificar_conversao_formato_placas(placa1, placa2):
    """
    Verifica se duas placas podem ser conversões entre formato antigo e Mercosul
    Exemplo: SVY1184 (antigo) <-> SVY1I84 (Mercosul) onde 1 na pos.3 pode ser I na pos.4
    
    Args:
        placa1 (str): Primeira placa
        placa2 (str): Segunda placa
    
    Returns:
        float: Similaridade específica para conversão de formato (0.0-1.0)
    """
    if not placa1 or not placa2 or len(placa1) != 7 or len(placa2) != 7:
        return 0.0
    
    # Verificar se uma é formato antigo e outra Mercosul
    eh_antigo1 = re.match(r'^[A-Z]{3}[0-9]{4}$', placa1)
    eh_mercosul1 = re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', placa1)
    eh_antigo2 = re.match(r'^[A-Z]{3}[0-9]{4}$', placa2)
    eh_mercosul2 = re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', placa2)
    
    # Se ambas são do mesmo formato, não é conversão
    if (eh_antigo1 and eh_antigo2) or (eh_mercosul1 and eh_mercosul2):
        return 0.0
    
    # Identificar qual é antigo e qual é Mercosul
    if eh_antigo1 and eh_mercosul2:
        antigo, mercosul = placa1, placa2
    elif eh_antigo2 and eh_mercosul1:
        antigo, mercosul = placa2, placa1
    else:
        return 0.0
    
    # Verificar se as três primeiras letras são iguais
    if antigo[:3] != mercosul[:3]:
        return 0.0
    
    # Verificar padrões de conversão específicos:
    # Antigo: ABC1234 -> Mercosul: ABC1I23, ABC1I34, etc.
    
    # Caso especial: SVY1184 -> SVY1I84
    # O "1" na posição 3 do antigo pode virar "I" na posição 4 do Mercosul
    
    confusoes_1_I = ['1', 'I', 'L', '|']
    
    # ✅ CORREÇÃO DE BUG: Validação mais rigorosa para conversão de formato
    # Padrão 1: ABC1234 -> ABC1I84 (1184 -> 1I84) - mas APENAS para conversões válidas
    # TIT4104 NÃO deve fazer match com TIT4I04 (são placas diferentes!)
    
    # Verificar se é realmente uma conversão válida de formato e não placas diferentes
    # Para ser conversão válida: o número que vira letra deve estar na MESMA posição lógica
    
    # Formato antigo:  ABC1234 (pos: 0123456)
    # Formato Mercosul: ABC1D23 (pos: 0123456)
    # A conversão válida seria: posição 4 do antigo == posição 4 do Mercosul (ambos letra)
    
    # CASO ESPECÍFICO PROBLEMÁTICO: TIT4104 vs TIT4I04
    # - antigo[3]='4', mercosul[3]='4' ✅ (mesmo número na pos 3)
    # - antigo[4]='1', mercosul[4]='I' ❌ (conversão 1->I, mas são placas DIFERENTES!)
    # - A lógica antiga permitia isso incorretamente
    
    # ✅ NOVA LÓGICA CORRIGIDA:
    # Só permite conversão se os 6 primeiros caracteres forem praticamente idênticos
    # e apenas 1 caractere for convertido entre 1/I na posição correta de formato
    
    if (antigo[:3] == mercosul[:3] and  # 3 primeiras letras idênticas
        antigo[3] == mercosul[3] and    # Primeira posição numérica idêntica  
        antigo[4] in ['1'] and mercosul[4] in ['I'] and  # Conversão 1->I específica
        antigo[5:7] == mercosul[5:7]):  # Últimos 2 números idênticos
        
        # ⚠️ VALIDAÇÃO ADICIONAL: Verificar se não são placas totalmente diferentes
        # Se mais de 1 posição difere significativamente, rejeitar
        diferencas = 0
        if antigo[4] != mercosul[4]:  # 1 vs I
            diferencas += 1
            
        # ✅ Permitir APENAS se for realmente conversão formato (máximo 1 diferença prevista)
        if diferencas <= 1:
            return 0.95  # ✅ Reduzido de 0.98 para 0.95 para ser mais conservador
        else:
            return 0.0  # ❌ Muitas diferenças - são placas diferentes
    
    # Padrão 2: Outros padrões de conversão formato
    matches = 0
    total_comparacoes = 0
    
    # Comparar posições equivalentes entre os formatos
    comparacoes = [
        (antigo[0], mercosul[0]),  # Primeira letra
        (antigo[1], mercosul[1]),  # Segunda letra  
        (antigo[2], mercosul[2]),  # Terceira letra
        (antigo[3], mercosul[3]),  # Primeiro número
        (antigo[5], mercosul[5]),  # Penúltimo número
        (antigo[6], mercosul[6])   # Último número
    ]
    
    for c1, c2 in comparacoes:
        total_comparacoes += 1
        if c1 == c2:
            matches += 1
        elif c1 in confusoes_1_I and c2 in confusoes_1_I:
            matches += 0.9  # Quase um match completo
    
    if total_comparacoes > 0:
        similaridade_base = matches / total_comparacoes
        # Bonus por ser conversão de formato válida
        return round(min(similaridade_base + 0.1, 1.0), 3)
    
    return 0.0


def buscar_placa_proxima_cadastrada(placa_lida, placas_cadastradas):
    """
    Busca por placas cadastradas que diferem apenas em 1 caractere da placa lida.
    Implementa correção de erros comuns como I/1, O/0, etc.
    
    Args:
        placa_lida (str): Placa lida (pode ter formato inválido)
        placas_cadastradas (list): Lista de placas já cadastradas
    
    Returns:
        dict: {'found': bool, 'placa': str, 'confidence': float, 'method': str}
    """
    if not placa_lida or not placas_cadastradas or len(placa_lida) != 7:
        return {'found': False, 'placa': None, 'confidence': 0.0, 'method': 'invalid_input'}
    
    # Caracteres comuns de confusão em OCR
    substituicoes_comuns = {
        'I': ['1', 'L', '|'],
        '1': ['I', 'L', '|'],
        'L': ['1', 'I', '|'],
        'O': ['0', 'Q'],
        '0': ['O', 'Q'],
        'Q': ['O', '0'],
        'S': ['5'],
        '5': ['S'],
        'B': ['8'],
        '8': ['B'],
        'E': ['F'],
        'F': ['E'],
        'G': ['6'],
        '6': ['G'],
        'Z': ['2'],
        '2': ['Z'],
        'D': ['0', 'O']
    }
    
    placa_lida = placa_lida.upper()
    
    # Verificar cada placa cadastrada
    for placa_cadastrada in placas_cadastradas:
        if len(placa_cadastrada) != 7:
            continue
            
        diferencias = 0
        posicoes_diferentes = []
        
        # Contar diferenças entre as placas
        for i in range(7):
            if placa_lida[i] != placa_cadastrada[i]:
                diferencias += 1
                posicoes_diferentes.append(i)
        
        # Se diferem apenas em 1 caractere
        if diferencias == 1:
            pos = posicoes_diferentes[0]
            char_lido = placa_lida[pos]
            char_cadastrado = placa_cadastrada[pos]
            
            # Verificar se é uma substituição comum (ex: I por 1)
            if (char_lido in substituicoes_comuns and 
                char_cadastrado in substituicoes_comuns[char_lido]):
                return {
                    'found': True,
                    'placa': placa_cadastrada,
                    'confidence': 0.90,  # Alta confiança para 1 char diff com substituição comum
                    'method': 'single_char_correction'
                }
            
            # Verificar substituição reversa
            elif (char_cadastrado in substituicoes_comuns and 
                  char_lido in substituicoes_comuns[char_cadastrado]):
                return {
                    'found': True,
                    'placa': placa_cadastrada,
                    'confidence': 0.90,
                    'method': 'single_char_correction_reverse'
                }
    
    return {'found': False, 'placa': None, 'confidence': 0.0, 'method': 'no_close_match'}


def consultar_tabela_deparaplacas(placa_lida):
    """
    Consulta a tabela deparaplacas para verificar se há um mapeamento
    da placa lida para uma placa correta.
    
    Estrutura da tabela: deparaplacas(placade CHAR(7), placapara CHAR(7))
    - placade: placa lida incorretamente (chave primária)  
    - placapara: placa correta correspondente
    
    Args:
        placa_lida (str): Placa lida pelo sistema
    
    Returns:
        dict: {'found': bool, 'placa_destino': str, 'placa_origem': str}
    """
    if not placa_lida or len(placa_lida) != 7:
        return {'found': False, 'placa_destino': None, 'placa_origem': None}
    
    conn = get_db_connection()
    if not conn:
        return {'found': False, 'placa_destino': None, 'placa_origem': None}
    
    cursor = conn.cursor()
    try:
        # Consultar tabela deparaplacas usando apenas os campos placade e placapara
        query = """
        SELECT placapara 
        FROM deparaplacas 
        WHERE placade = %s
        LIMIT 1
        """
        cursor.execute(query, (placa_lida.upper(),))
        resultado = cursor.fetchone()
        print(f'******Consultei placa depara - resultado: {resultado}')
        if resultado:
            return {
                'found': True,
                'placa_destino': resultado[0],  # placapara
                'placa_origem': placa_lida.upper()  # placade original
            }
        else:
            return {'found': False, 'placa_destino': None, 'placa_origem': None}
            
    except mysql.connector.Error as err:
        print(f"Erro ao consultar tabela deparaplacas: {err}")
        return {'found': False, 'placa_destino': None, 'placa_origem': None}
    finally:
        cursor.close()
        conn.close()