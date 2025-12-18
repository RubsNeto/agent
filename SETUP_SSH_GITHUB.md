# 🔐 Configuração de SSH para GitHub Actions

> Guia passo a passo para gerar chave SSH e configurar no GitHub/Servidor.

---

## 📋 Passo 1: Gerar Chave SSH (No seu PC)

Abra o **PowerShell** e execute:

```powershell
ssh-keygen -t ed25519 -C "github-actions-deploy" -f $HOME\.ssh\github_actions_key
```

> **Nota:** Quando pedir senha (passphrase), deixe em branco (pressione Enter duas vezes).

Isso cria dois arquivos:
- `~/.ssh/github_actions_key` → **Chave Privada** (vai no GitHub)
- `~/.ssh/github_actions_key.pub` → **Chave Pública** (vai no servidor)

---

## 📋 Passo 2: Copiar Chave Pública para o Servidor

Execute no PowerShell:

```powershell
# Ver conteúdo da chave pública
Get-Content $HOME\.ssh\github_actions_key.pub
```

Copie o resultado e depois conecte no servidor:

```powershell
ssh root@31.97.95.233
```

No servidor, adicione a chave pública:

```bash
# Adicionar ao authorized_keys
echo "COLE_A_CHAVE_PUBLICA_AQUI" >> ~/.ssh/authorized_keys

# Ajustar permissões (importante!)
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

---

## 📋 Passo 3: Configurar Secrets no GitHub

1. Acesse: https://github.com/RubsNeto/agent/settings/secrets/actions
2. Clique em **"New repository secret"**
3. Crie os seguintes secrets:

### Secret 1: SSH_HOST
```
Name: SSH_HOST
Value: 31.97.95.233
```

### Secret 2: SSH_USER
```
Name: SSH_USER
Value: root
```

### Secret 3: SSH_PRIVATE_KEY
```
Name: SSH_PRIVATE_KEY
Value: (conteúdo da chave PRIVADA)
```

Para ver a chave privada, execute no PowerShell:
```powershell
Get-Content $HOME\.ssh\github_actions_key
```

⚠️ **IMPORTANTE:** Cole TODO o conteúdo, incluindo:
```
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

---

## 📋 Passo 4: Testar o Deploy

### Opção A: Push na branch main
```powershell
git add .
git commit -m "Testar CI/CD"
git push origin main
```

### Opção B: Executar manualmente
1. Vá em: https://github.com/RubsNeto/agent/actions
2. Clique em "Deploy to Production"
3. Clique em "Run workflow"

---

## ✅ Verificar se Funcionou

1. Acesse: https://github.com/RubsNeto/agent/actions
2. Veja se a execução ficou verde ✅
3. Clique para ver os logs se houver erro

---

## 🔧 Troubleshooting

### Erro "Permission denied"
- Verifique se a chave pública está no `~/.ssh/authorized_keys` do servidor
- Verifique as permissões: `chmod 600 ~/.ssh/authorized_keys`

### Erro "Host key verification failed"
- Adicione `StrictHostKeyChecking: no` no workflow (já está configurado)

### Erro "docker: command not found"
- Docker não está instalado ou não está no PATH do usuário root

---

**Links úteis:**
- [GitHub Actions Secrets](https://github.com/RubsNeto/agent/settings/secrets/actions)
- [Actions Logs](https://github.com/RubsNeto/agent/actions)
