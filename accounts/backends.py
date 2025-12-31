from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """
    Autentica usando email ou username.
    Permite que o usuário faça login com email ou username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        
        if username is None or password is None:
            return None
        
        try:
            # Tenta encontrar o usuário por email ou username
            # Usar Q objects para busca flexível
            user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
            
            if not user:
                logger.warning(f"Login falhou: usuário '{username}' não encontrado.")
                return None
                
            # Verifica a senha e se pode autenticar (ativo)
            if user.check_password(password) and self.user_can_authenticate(user):
                logger.info(f"Usuário '{user.username}' autenticado com sucesso.")
                return user
            elif not self.user_can_authenticate(user):
                logger.warning(f"Login falhou: usuário '{username}' inativo.")
            else:
                logger.warning(f"Login falhou: senha incorreta para '{username}'.")
                
        except Exception as e:
            logger.error(f"Erro no backend de autenticação: {e}")
            return None
        
        return None
