# parkvision
Desenvolvimento de gestão de estacionamento

Descrição das tabelas do banco de dados

Tabela: cadveiculo
Descrição da tabela: Cadastro básico de veículos
Chave primária: placa
Campo;Tipo;Descrição;Restrição
placa;Char(7);Placa do veículo;Formatos de placas válidos
idmodelo;int;Código do modelo (relação tabela cadmodelo);Deve existir na tabela cadmodelo
cor;Varchar(30);Cor do veículo;N/A
lup;datetime;Momento da última atualização;Atualizado automaticamente


Tabela: cadlocal
Descrição da tabela: Localização atual dos veículos nos condomínios
Chave primária: idcond, placa, unidade
Campo;Tipo;Descrição;Restrição
idcond;Int;Código do condomínio (relação tabela cadcond);Não Nulo
placa;Char(7);Placa do veículo;Formatos de placas válidos
unidade;Varchar(10);Unidade/apartamento no condomínio;Não nulo
sit;Int;Situação: 1=Dentro, 0=Fora;Zero ou Um
lup;datetime;Momento da última atualização;Atualizado automaticamente


Tabela: cadperm
Descrição da tabela: Permissões de estacionamento por período
Chave primária: idcond, placa, data_inicio
Campo;Tipo;Descrição;Restrição
idcond;Int;Código do condomínio (relação tabela cadcond);Não Nulo
placa;Char(7);Placa do veículo;Formatos de placas válidos
unidade;Varchar(10);Unidade/apartamento no condomínio;Não nulo
data_inicio;Date;Data de início da permissão;Data válida
data_fim;Date;Data de fim da permissão;Pode ser nula e quando não nula deve ser posterior a data_inicio
lup;Datetime;Momento da última atualização;Atualizado automaticamente


Tabela: cadcond
Descrição da Tabela: Condomínios
Chave primária: idcond
Campo;Tipo;Descrição;Restrição
idcond;Int;Código do condomínio;autoincremento
nmcond;Varchar(50);Nome do condomínio;N/A
nrcond;Int;Número do condomínio dentro do sistema do cliente;N/A
idemp;Int;Id da empresa (relação tabela cademp);N/A
cicond;Varchar(50);Cidade do condomínio;N/A


Tabela: cademp
Descrição da Tabela: Empresas (clientes)
Chave primária: idemp
Campo;Tipo;Descrição;Restrição
idemp;Int;Código da empresa (cliente);autoincremento
nmemp;Varchar(30);Nome da empresa (cliente);N/A


Tabela: cadmarca
Descrição da Tabela: Marcas de veículos
Chave primária: idmarca
Campo;Tipo;Descrição;Restrição
idmarca;Int;Código da marca;autoincremento
nmmarca;Varchar(50);Nome da marca;N/A


Tabela: cadmodelo
Descrição da Tabela: Modelos de veículos
Chave primária: idmarca
Campo;Tipo;Descrição;Restrição
idmodelo;Int;Código do modelo;autoincremento
nmmodelo;Varchar(50);Nome do modelo;N/A
idmarca;int;Id da marca (relação tabela cadmarca);N/A


Tabela: vagasunidades
Descrição da Tabela: Vagas permitidas por unidade
Chave primária: idcond, unidade
Campo;Tipo;Descrição;Restrição
idcond;Int;Código do condomínio (relação tabela cadcond);Não Nulo
unidade;Varchar(10);Unidade/apartamento no condomínio;Não nulo
vperm;Int;Quantidades de vagas permitidas;N/A
vocup;Int;Quantidade de vagas ocupadas;N/A
Seqcond;Int;Sequência de unidades interna, usado para reports e quadros;N/A
lup;Datetime;Momento da última atualização;Atualizado automaticamente


Tabela: semcadastro
Descrição da tabela: Veículos que apareceram no condomínio e não estão cadastrados
Chave primária: idseq
Campo;Tipo;Descrição;Restrição
Idseq;Int;Id sequencial;autoincremento
idcond;Int;Código do condomínio (relação tabela cadcond);Não Nulo
placa;Char(7);Placa do veículo;N/A
lup;Datetime;Momento da última atualização;Atualizado automaticamente


Tabela: movcar
Descrição da tabela: contém os carros identificados pelo heimdall (que envia as informações abaixo que são armazenadas no banco de dados)
Chave primária: idmov
Campo;Tipo;Descrição;Restrição
idmov;Int;Id sequencial;autoincremento
idlog;Int;Id do log do heimdall;N/A
idcond;Int;Código do condomínio (relação tabela cadcond);N/A
placa;Char(7);Placa do veículo;N/A
nowpost;datetime;momento em que o carro foi identificado pelo heimdall;N/A
cor;Varchar(50);cor do carro identificado pelo heimdall;N/A
corconf;float;Percentual de confiabilidade da cor do carro;N/A
ender;Varchar(100);endereço da câmera;N/A
nomecam;Varchar(30);nome da câmera;N/A
idcam;Int;identificação da câmera;N/A
idaia;Int;Identificação do analítico;N?a



Tabela: cadcar (será extinta)
Descrição da tabela: Contém os veículos trabalhados
Chave primária: idmov
Campo;Tipo;Descrição;Restrição
idcond;Int;Código do condomínio (relação tabela cadcond);Não Nulo
placa;Char(7);Placa do veículo;Formatos de placas válidos
unidade;Varchar(10);Unidade/apartamento no condomínio;Não nulo
idmodelo;int;Código do modelo (relação tabela cadmodelo);Deve existir na tabela cadmodelo
cor;Varchar(30);Cor do veículo;N/A
sit;Char(1);situação do veículo: (D) dentro do condomínio ou (F) fora do condomínio;D ou F
lastupdate;Datetime;Momento da última atualização;Atualizado automaticamente

