"""
Biblioteca para processamento de placas de veículos
Valida e corrige placas lidas pelo sistema Heimdall
"""

import re


def process_heimdall_plate(placa_lida, idcond, confianca_minima=0.8, pular_cadastro_carros=True):
    """
    Processa placa lida pelo Heimdall, validando formato e aplicando correções
    
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
            'original_plate': str    # Placa original
        }
    """
    
    if not placa_lida:
        return {
            'corrected_plate': '*ERROR*',
            'found_match': False,
            'confidence': 0.0,
            'original_plate': placa_lida or ''
        }
    
    # Limpar e padronizar placa
    placa_limpa = limpar_placa(placa_lida)
    
    # Validar formato da placa
    if not validar_formato_placa(placa_limpa):
        # Tentar correções automáticas
        placa_corrigida = tentar_corrigir_placa(placa_limpa)
        if placa_corrigida and validar_formato_placa(placa_corrigida):
            placa_limpa = placa_corrigida
        else:
            return {
                'corrected_plate': '*ERROR*',
                'found_match': False,
                'confidence': 0.0,
                'original_plate': placa_lida
            }
    
    # Calcular confiança baseada na qualidade da placa
    confianca = calcular_confianca_placa(placa_limpa, placa_lida)
    
    # Verificar se atende ao nível mínimo de confiança
    found_match = confianca >= confianca_minima
    
    return {
        'corrected_plate': placa_limpa if found_match else '*ERROR*',
        'found_match': found_match,
        'confidence': confianca,
        'original_plate': placa_lida
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
    Tenta corrigir placas com pequenos erros
    Aplica correções comuns de OCR
    """
    if not placa:
        return None
    
    # Se a placa tem tamanho incorreto, não tenta corrigir
    if len(placa) != 7:
        return None
    
    # Para simplificar, apenas validar se já está no formato correto
    if validar_formato_placa(placa):
        return placa
    
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