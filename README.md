# Jobot

Um conjunto de bots para realizar scraping em vagas de emprego.

## Pré-requisitos

- Python
- Docker _(para o banco de dados MongoDB)_

## Instruções

1. Instale as dependências.
   ```
   pip install -r requirements.txt
   ```
2. Configure o arquivo [configs.yml](#configyml).
3. Defina as [variáveis de ambiente](#variáveis-de-ambiente).

## Configurações

### Config.yml

Antes de executar o bot, é necessário fazer algumas configurações no arquivo `configs.yml`.

1. **Definir as pesquisas**

   Atualmente há 3 bots: indeedbot, infojobbot, linkedinbot.

   **Dica**: Faça um pesquisa diretamente nos sites alvos para saber o formato das **localizações** de cada um, para evitar erros.

   Exemplo:

   ```yaml
   searches:
     indeedbot:
       - job: desenvolvedor
         locations: ["Rio de Janeiro, RJ", "Remoto"]
   ```

2. **Definir os filtros (opcional)**

   Filtre os melhores resultados obtidos nas pesquisas, em diferentes campos.

   Caso defina filtros, os resultados encontrados precisarão passa por todos esses filtros para serem salvos no banco de dados.

   Exemplo:

   ```yaml
   filters:
     - key: title # title, description, company
       full_match: False # False = No mínimo uma palavra precisa está incluída | True = TODAS as palavras precisam está incluídas
       include: # Palavras ou frases que precisam está INCLUÍDAS nos resultados
         - lista: ["qualquer", "coisa"]
         - outra_lista: ["qualquer", "coisa"]
       exclude: # Palavras ou frases que NÃO devem está incluídas nos resultados
         - lista: ["qualquer", "coisa"]
         - outra_lista: ["qualquer", "coisa"]
   ```

### Variáveis de Ambiente

Alguns sites impõe limites nos resultados de pesquisas para usuários não-autenticados, portanto se não estiver obtendo muitos resultados, experimente definir suas credenciais nas variáveis de ambiente.

Crie um arquivo `.env` na diretório raiz do projeto com as seguintes variáveis:

```env
DB_HOST=mongodb://root:example@localhost:27017

INDEED_USER=
INDEED_PASS=

INFOJOB_USER=
INFOJOB_PASS=

LINKEDIN_USER=
LINKEDIN_PASS=
```
