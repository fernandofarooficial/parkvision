-- SCRIPT DE MIGRAÇÃO PARA SISTEMA DE AUTENTICAÇÃO POR USUÁRIO
-- Execute estas queries no banco de dados MySQL

-- 1. Tabela de usuários
CREATE TABLE usuarios (
    idgente INT AUTO_INCREMENT PRIMARY KEY,
    nome_completo VARCHAR(100) NOT NULL,
    nome_curto VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    telefone VARCHAR(20),
    senha_hash VARCHAR(255) NOT NULL,
    tipo_usuario ENUM('ADM', 'MONITOR', 'SINDICO') NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lup TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_tipo_usuario (tipo_usuario)
);

-- 2. Tabela de permissões de usuário por condomínio
CREATE TABLE usuario_condominios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    idgente INT NOT NULL,
    idcond INT NOT NULL,
    data_liberacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    liberado_por INT NOT NULL, -- idgente do usuário que liberou
    lup TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (idgente) REFERENCES usuarios(idgente) ON DELETE CASCADE,
    FOREIGN KEY (idcond) REFERENCES cadcond(idcond) ON DELETE CASCADE,
    FOREIGN KEY (liberado_por) REFERENCES usuarios(idgente),
    UNIQUE KEY unique_user_condo (idgente, idcond)
);

-- 3. Tabela de solicitações de inscrição
CREATE TABLE solicitacoes_inscricao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome_completo VARCHAR(100) NOT NULL,
    nome_curto VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    telefone VARCHAR(20),
    tipo_usuario_solicitado ENUM('MONITOR', 'SINDICO') NOT NULL,
    justificativa TEXT,
    status ENUM('PENDENTE', 'APROVADO', 'REJEITADO') DEFAULT 'PENDENTE',
    data_solicitacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_resposta TIMESTAMP NULL,
    respondido_por INT NULL, -- idgente do ADM que respondeu
    observacoes_resposta TEXT NULL,
    lup TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (respondido_por) REFERENCES usuarios(idgente),
    INDEX idx_status (status),
    INDEX idx_email_solicitacao (email)
);

-- 4. Tabela de tokens de recuperação de senha
CREATE TABLE tokens_recuperacao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    idgente INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    expira_em TIMESTAMP NOT NULL,
    usado BOOLEAN DEFAULT FALSE,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (idgente) REFERENCES usuarios(idgente) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_expiracao (expira_em)
);

-- 5. Tabela de log de ações de usuários (auditoria)
CREATE TABLE log_usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    idgente INT NOT NULL,
    acao VARCHAR(100) NOT NULL,
    detalhes TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    data_acao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (idgente) REFERENCES usuarios(idgente) ON DELETE CASCADE,
    INDEX idx_usuario_acao (idgente, acao),
    INDEX idx_data (data_acao)
);

-- 6. Inserir usuário administrador padrão
-- SENHA TEMPORÁRIA: admin123 (ALTERAR APÓS PRIMEIRO LOGIN)
INSERT INTO usuarios (nome_completo, nome_curto, email, telefone, senha_hash, tipo_usuario) 
VALUES ('Administrador do Sistema', 'Admin', 'admin@parkvision.com', '(11) 99999-9999', 
        '$2b$12$GXXfgPXvRvM5o9pL8ZpNKeEKvLHfWQXNu5rX3VJ8U5p4r6Y1W0O4q', 'ADM');

-- 7. View para consulta completa de usuários com permissões
CREATE VIEW vw_usuarios_completo AS
SELECT 
    u.idgente,
    u.nome_completo,
    u.nome_curto,
    u.email,
    u.telefone,
    u.tipo_usuario,
    u.ativo,
    u.data_criacao,
    GROUP_CONCAT(DISTINCT c.nmcond ORDER BY c.nmcond SEPARATOR ', ') as condominios_permitidos,
    COUNT(DISTINCT uc.idcond) as total_condominios
FROM usuarios u
LEFT JOIN usuario_condominios uc ON u.idgente = uc.idgente
LEFT JOIN cadcond c ON uc.idcond = c.idcond
WHERE u.ativo = TRUE
GROUP BY u.idgente, u.nome_completo, u.nome_curto, u.email, u.telefone, u.tipo_usuario, u.ativo, u.data_criacao;

-- 8. View para relatório de solicitações pendentes
CREATE VIEW vw_solicitacoes_pendentes AS
SELECT 
    s.id,
    s.nome_completo,
    s.nome_curto,
    s.email,
    s.telefone,
    s.tipo_usuario_solicitado,
    s.justificativa,
    s.data_solicitacao,
    TIMESTAMPDIFF(DAY, s.data_solicitacao, NOW()) as dias_pendente
FROM solicitacoes_inscricao s
WHERE s.status = 'PENDENTE'
ORDER BY s.data_solicitacao ASC;

-- COMENTÁRIOS SOBRE AS MODIFICAÇÕES:
-- 
-- 1. A tabela 'usuarios' substitui o sistema atual de senhas hardcoded
-- 2. 'usuario_condominios' controla quais condomínios cada usuário pode acessar
-- 3. 'solicitacoes_inscricao' gerencia pedidos de cadastro
-- 4. 'tokens_recuperacao' para funcionalidade "esqueci minha senha"
-- 5. 'log_usuarios' para auditoria e segurança
-- 
-- NÍVEIS DE ACESSO:
-- - ADM: Acesso total, pode gerenciar usuários e todos os condomínios
-- - MONITOR: Pode editar e visualizar, limitado aos condomínios liberados
-- - SINDICO: Apenas visualização e relatórios, limitado aos condomínios liberados
--
-- SEGURANÇA:
-- - Senhas são hasheadas usando bcrypt
-- - Tokens de recuperação têm expiração
-- - Log de auditoria para ações críticas
-- - Índices para performance em consultas de autenticação